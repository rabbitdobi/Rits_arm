import SwiftUI

struct ContentView: View {
    @StateObject private var capture = CaptureController()
    @Environment(\.scenePhase) private var scenePhase
    @State private var camera = DepthCamera.front
    @State private var reference = ""
    @State private var now = Date()
    private let timer = Timer.publish(every: 0.25, on: .main, in: .common).autoconnect()

    private var fresh: FrameReading? {
        guard let reading = capture.reading, now.timeIntervalSince(reading.timestamp) < 1 else { return nil }
        return reading
    }

    private var referenceCM: Double? {
        let value = Double(reference.replacingOccurrences(of: ",", with: "."))
        return value.flatMap { $0.isFinite && $0 > 0 ? $0 : nil }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    Picker("Depth camera", selection: $camera) {
                        ForEach(capture.availableCameras) { Text($0.title).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .disabled(capture.isRecording)

                    if let reading = capture.reading {
                        Image(uiImage: reading.image)
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .overlay {
                                GeometryReader { geometry in
                                    Rectangle().stroke(.yellow, lineWidth: 2)
                                        .frame(width: geometry.size.width * 0.06, height: geometry.size.height * 0.06)
                                        .position(x: geometry.size.width / 2, y: geometry.size.height / 2)
                                }
                            }
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .opacity(fresh == nil ? 0.4 : 1)
                    } else {
                        RoundedRectangle(cornerRadius: 12).fill(.black)
                            .frame(height: 240)
                            .overlay { Text("Waiting for synchronized video + depth").foregroundStyle(.white).padding() }
                    }

                    Text(fresh?.statistics.medianMeters.map { String(format: "%.1f cm", $0 * 100) } ?? "— cm")
                        .font(.system(size: 44, weight: .semibold, design: .rounded))
                        .monospacedDigit()
                        .accessibilityLabel("Center depth")
                    Text(capture.status).font(.subheadline).multilineTextAlignment(.center)
                    if capture.reading != nil && fresh == nil {
                        Text("No fresh frame — distance hidden").foregroundStyle(.orange)
                    }
                    if let reading = fresh {
                        HStack {
                            metric("Valid pixels", String(format: "%.0f%%", reading.statistics.validFraction * 100))
                            Spacer()
                            metric("Jitter · last 30 frames", reading.jitterMeters.map { String(format: "%.2f cm", $0 * 100) } ?? "—")
                        }
                        Text(reading.format).font(.caption).foregroundStyle(.secondary)
                        Text("Sensor reports \(reading.accuracy) accuracy; values converted from meters to cm.")
                            .font(.caption).foregroundStyle(reading.accuracy == "relative" ? Color.orange : Color.secondary)
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        Text("Compare the two cameras").font(.headline)
                        Text("Fix the phone in one position. Fill the yellow center box with your palm and hold still for each 10-second test.")
                            .font(.subheadline)
                        TextField("Measured reference distance in cm (optional)", text: $reference)
                            .keyboardType(.decimalPad)
                            .textFieldStyle(.roundedBorder)
                            .disabled(capture.isRecording)
                        if !reference.isEmpty && referenceCM == nil {
                            Text("Enter a positive distance, or leave it empty.").font(.caption).foregroundStyle(.red)
                        }
                        Button(capture.isRecording ? "Recording 10-second test…" : "Record 10-second test") {
                            capture.startTest(referenceCM: referenceCM)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(fresh == nil || capture.isRecording || (!reference.isEmpty && referenceCM == nil))
                        if let url = capture.savedCSV {
                            ShareLink("Share last CSV", item: url)
                            Text(url.lastPathComponent).font(.caption2).textSelection(.enabled)
                        }
                    }
                    .padding().background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))

                    Text("Center-patch median · depth filtering OFF · not finger tracking yet. Low jitter does not prove accurate distance. No audio or network transmission.")
                        .font(.caption).foregroundStyle(.secondary)
                    Button("Retry camera") { capture.start(camera, force: true) }.disabled(capture.isRecording)
                }
                .padding()
            }
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle("Depth Probe")
            .task {
                if !capture.availableCameras.contains(camera), let first = capture.availableCameras.first { camera = first }
                capture.start(camera)
            }
            .onChange(of: camera) { _, selected in capture.start(selected) }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { capture.start(camera) }
                else { capture.stop() }
            }
            .onReceive(timer) { now = $0 }
        }
    }

    private func metric(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.headline).monospacedDigit()
        }
    }
}
