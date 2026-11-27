import AVFoundation
import Combine
import CoreImage
import UIKit

enum DepthCamera: String, CaseIterable, Identifiable {
    case front, rear
    var id: String { rawValue }
    var title: String { self == .front ? "Front TrueDepth" : "Rear LiDAR" }
    var position: AVCaptureDevice.Position { self == .front ? .front : .back }
    var type: AVCaptureDevice.DeviceType { self == .front ? .builtInTrueDepthCamera : .builtInLiDARDepthCamera }
    var device: AVCaptureDevice? { AVCaptureDevice.default(type, for: .video, position: position) }
}

struct FrameReading {
    let image: UIImage
    let statistics: PatchStatistics
    let jitterMeters: Double?
    let timestamp: Date
    let format: String
    let accuracy: String
}

/// Capture, camera switching and CSV accumulation are confined to one serial queue.
final class CaptureController: NSObject, ObservableObject, AVCaptureDataOutputSynchronizerDelegate {
    @Published private(set) var reading: FrameReading?
    @Published private(set) var status = "Camera is stopped"
    @Published private(set) var isRecording = false
    @Published private(set) var savedCSV: URL?
    let availableCameras = DepthCamera.allCases.filter { $0.device != nil }

    private let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "DepthProbe.capture")
    private let context = CIContext(options: [.cacheIntermediates: false])
    private var videoOutput: AVCaptureVideoDataOutput?
    private var depthOutput: AVCaptureDepthDataOutput?
    private var synchronizer: AVCaptureDataOutputSynchronizer?
    private var device: AVCaptureDevice?
    private var camera = DepthCamera.front
    private var wanted = false
    private var window = DepthWindow(capacity: 30)
    private var lastPublish = -Double.infinity
    private var test: TestRun?
    private var observers: [NSObjectProtocol] = []

    private struct TestRun {
        let id = UUID()
        let started = ProcessInfo.processInfo.systemUptime
        let referenceCM: Double?
        var rows: [DepthRow] = []
    }

    override init() {
        super.init()
        for name in [AVCaptureSession.wasInterruptedNotification,
                     AVCaptureSession.runtimeErrorNotification] {
            observers.append(NotificationCenter.default.addObserver(forName: name, object: session, queue: nil) { [weak self] _ in
                self?.queue.async { [weak self] in
                    guard let self = self else { return }
                    self.finishTest()
                    self.window = DepthWindow(capacity: 30)
                    self.publishStatus("Capture interrupted. Return to the app or tap Retry.", clear: true)
                }
            })
        }
    }

    deinit { observers.forEach(NotificationCenter.default.removeObserver) }

    func start(_ selected: DepthCamera, force: Bool = false) {
        queue.async {
            self.wanted = true
            switch AVCaptureDevice.authorizationStatus(for: .video) {
            case .authorized:
                self.configureAndStart(selected, force: force)
            case .notDetermined:
                self.publishStatus("Allow camera access to measure depth", clear: true)
                AVCaptureDevice.requestAccess(for: .video) { granted in
                    self.queue.async {
                        guard self.wanted else { return }
                        if granted { self.configureAndStart(selected, force: force) }
                        else { self.publishStatus("Camera access denied. Enable it in Settings > Depth Probe.", clear: true) }
                    }
                }
            default:
                self.publishStatus("Camera access denied. Enable it in Settings > Depth Probe.", clear: true)
            }
        }
    }

    func stop() {
        queue.async {
            self.wanted = false
            self.session.stopRunning()
            self.finishTest()
            self.window = DepthWindow(capacity: 30)
            self.publishStatus("Camera paused", clear: true)
        }
    }

    private func configureAndStart(_ selected: DepthCamera, force: Bool) {
        if session.isRunning, camera == selected, !force { return }
        session.stopRunning()
        finishTest()
        publishStatus("Starting \(selected.title)…", clear: true)
        do {
            try configure(selected)
            guard wanted else { return }
            session.startRunning()
            publishStatus(session.isRunning ? "Aim the center box at your palm" : "Camera did not start. Tap Retry.", clear: false)
        } catch {
            publishStatus(error.localizedDescription, clear: true)
        }
    }

    private func configure(_ selected: DepthCamera) throws {
        guard let cameraDevice = selected.device else { throw failure("\(selected.title) is unavailable on this device.") }
        synchronizer?.setDelegate(nil, queue: nil)
        synchronizer = nil
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        session.inputs.forEach(session.removeInput)
        session.outputs.forEach(session.removeOutput)
        session.sessionPreset = .inputPriority
        let input = try AVCaptureDeviceInput(device: cameraDevice)
        guard session.canAddInput(input) else { throw failure("Cannot add camera input.") }
        session.addInput(input)

        let formats = cameraDevice.formats.filter {
            !$0.supportedDepthDataFormats.isEmpty &&
            CMFormatDescriptionGetMediaSubType($0.formatDescription) == kCVPixelFormatType_420YpCbCr8BiPlanarFullRange
        }.sorted {
            let a = CMVideoFormatDescriptionGetDimensions($0.formatDescription)
            let b = CMVideoFormatDescriptionGetDimensions($1.formatDescription)
            // Prefer a modest video resolution for preview CPU cost.
            return abs(Int(a.width) - 1280) < abs(Int(b.width) - 1280)
        }
        var chosen: (AVCaptureDevice.Format, AVCaptureDevice.Format, Int32)?
        for format in formats {
            let depths = format.supportedDepthDataFormats.sorted {
                CMVideoFormatDescriptionGetDimensions($0.formatDescription).width > CMVideoFormatDescriptionGetDimensions($1.formatDescription).width
            }
            for depth in depths {
                for fps: Int32 in [30, 24, 15] {
                    let supported: (AVCaptureDevice.Format) -> Bool = { format in
                        format.videoSupportedFrameRateRanges.contains { $0.minFrameRate <= Double(fps) && $0.maxFrameRate >= Double(fps) }
                    }
                    if supported(format) && supported(depth) {
                        chosen = (format, depth, fps)
                        break
                    }
                }
                if chosen != nil { break }
            }
            if chosen != nil { break }
        }
        guard let (format, depthFormat, fps) = chosen else { throw failure("No compatible video/depth format at 15–30 FPS.") }
        try cameraDevice.lockForConfiguration()
        cameraDevice.activeFormat = format
        cameraDevice.activeDepthDataFormat = depthFormat
        cameraDevice.activeVideoMinFrameDuration = CMTime(value: 1, timescale: fps)
        cameraDevice.activeVideoMaxFrameDuration = CMTime(value: 1, timescale: fps)
        cameraDevice.unlockForConfiguration()

        let video = AVCaptureVideoDataOutput()
        video.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        video.alwaysDiscardsLateVideoFrames = true
        let depth = AVCaptureDepthDataOutput()
        depth.isFilteringEnabled = false // Same setting for both cameras; no hole filling.
        depth.alwaysDiscardsLateDepthData = true
        guard session.canAddOutput(video), session.canAddOutput(depth) else { throw failure("Cannot add synchronized capture outputs.") }
        session.addOutput(video)
        session.addOutput(depth)
        for connection in [video.connection(with: .video), depth.connection(with: .depthData)].compactMap({ $0 }) {
            if connection.isVideoOrientationSupported { connection.videoOrientation = .portrait }
            if connection.isVideoMirroringSupported {
                connection.automaticallyAdjustsVideoMirroring = false
                connection.isVideoMirrored = false
            }
        }
        videoOutput = video
        depthOutput = depth
        device = cameraDevice
        camera = selected
        window = DepthWindow(capacity: 30)
        lastPublish = -.infinity
        let sync = AVCaptureDataOutputSynchronizer(dataOutputs: [video, depth])
        sync.setDelegate(self, queue: queue)
        synchronizer = sync
    }

    func dataOutputSynchronizer(_ synchronizer: AVCaptureDataOutputSynchronizer,
                               didOutput collection: AVCaptureSynchronizedDataCollection) {
        guard wanted, synchronizer === self.synchronizer,
              let videoOutput = videoOutput, let depthOutput = depthOutput else { return }
        guard let video = collection.synchronizedData(for: videoOutput) as? AVCaptureSynchronizedSampleBufferData,
              let depth = collection.synchronizedData(for: depthOutput) as? AVCaptureSynchronizedDepthData,
              !video.sampleBufferWasDropped, !depth.depthDataWasDropped,
              let colorBuffer = CMSampleBufferGetImageBuffer(video.sampleBuffer) else {
            recordInvalidFrame()
            return
        }
        let converted = depth.depthData.converting(toDepthDataType: kCVPixelFormatType_DepthFloat32)
        let buffer = converted.depthDataMap
        let statistics = centerStatistics(buffer)
        let accuracy = converted.depthDataAccuracy == .absolute ? "absolute" : "relative"
        let timestamp = CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(video.sampleBuffer))
        let jitter = window.update(meters: statistics.medianMeters, timestamp: timestamp)
        appendTest(statistics: statistics, jitter: jitter, accuracy: accuracy)
        let now = ProcessInfo.processInfo.systemUptime
        guard now - lastPublish >= 0.1 else { return }
        lastPublish = now
        let ciImage = CIImage(cvPixelBuffer: colorBuffer)
        guard let cgImage = context.createCGImage(ciImage, from: ciImage.extent) else { return }
        let dimensions = "Video \(CVPixelBufferGetWidth(colorBuffer))×\(CVPixelBufferGetHeight(colorBuffer)); depth \(CVPixelBufferGetWidth(buffer))×\(CVPixelBufferGetHeight(buffer))"
        let reading = FrameReading(image: UIImage(cgImage: cgImage), statistics: statistics,
                                   jitterMeters: jitter, timestamp: Date(), format: dimensions, accuracy: accuracy)
        DispatchQueue.main.async {
            self.reading = reading
            self.status = statistics.medianMeters == nil ? "Not enough valid depth in center box" : "Center depth in centimeters — hold still to compare"
        }
    }

    private func centerStatistics(_ buffer: CVPixelBuffer) -> PatchStatistics {
        guard CVPixelBufferGetPixelFormatType(buffer) == kCVPixelFormatType_DepthFloat32,
              CVPixelBufferLockBaseAddress(buffer, .readOnly) == kCVReturnSuccess else { return .measure([]) }
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(buffer) else { return .measure([]) }
        let width = CVPixelBufferGetWidth(buffer), height = CVPixelBufferGetHeight(buffer)
        let stride = CVPixelBufferGetBytesPerRow(buffer)
        return CenterPatch.measure(base: base, width: width, height: height, bytesPerRow: stride)
    }

    func startTest(referenceCM: Double?) {
        queue.async {
            guard self.session.isRunning, self.test == nil else { return }
            self.test = TestRun(referenceCM: referenceCM)
            let id = self.test!.id
            DispatchQueue.main.async { self.isRecording = true; self.savedCSV = nil }
            self.queue.asyncAfter(deadline: .now() + 10) {
                if self.test?.id == id { self.finishTest() }
            }
        }
    }

    private func appendTest(statistics: PatchStatistics, jitter: Double?, accuracy: String = "unknown") {
        guard test != nil else { return }
        test!.rows.append(DepthRow(elapsedSeconds: ProcessInfo.processInfo.systemUptime - test!.started,
                                   meters: statistics.medianMeters, validFraction: statistics.validFraction,
                                   spatialSDMeters: statistics.spatialSDMeters, temporalSDMeters: jitter, accuracy: accuracy))
    }

    private func recordInvalidFrame() {
        window = DepthWindow(capacity: 30)
        appendTest(statistics: .measure([]), jitter: nil)
        DispatchQueue.main.async { self.reading = nil; self.status = "Synchronized frame dropped — waiting for fresh depth" }
    }

    private func finishTest() {
        guard let run = test else { return }
        test = nil
        DispatchQueue.main.async { self.isRecording = false }
        guard !run.rows.isEmpty else { publishStatus("No synchronized frames received; no test saved.", clear: false); return }
        do {
            let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let url = directory.appendingPathComponent("depth-\(camera.rawValue)-\(run.id.uuidString).csv")
            let csv = DepthCSV.render(rows: run.rows, camera: camera.title, cameraID: device?.uniqueID ?? "unknown",
                                      phoneModel: Self.hardwareModel(), systemVersion: ProcessInfo.processInfo.operatingSystemVersionString,
                                      referenceCM: run.referenceCM)
            try csv.write(to: url, atomically: true, encoding: .utf8)
            DispatchQueue.main.async { self.savedCSV = url }
        } catch { publishStatus("CSV save failed: \(error.localizedDescription)", clear: false) }
    }

    private func publishStatus(_ message: String, clear: Bool) {
        DispatchQueue.main.async { self.status = message; if clear { self.reading = nil } }
    }

    private func failure(_ message: String) -> NSError {
        NSError(domain: "DepthProbe", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
    }

    private static func hardwareModel() -> String {
        var info = utsname()
        uname(&info)
        let size = MemoryLayout.size(ofValue: info.machine)
        return withUnsafePointer(to: &info.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: size) { String(cString: $0) }
        }
    }
}
