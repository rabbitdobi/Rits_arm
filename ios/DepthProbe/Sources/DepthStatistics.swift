import Foundation

enum CenterPatch {
    static func measure(base: UnsafeRawPointer, width: Int, height: Int, bytesPerRow: Int) -> PatchStatistics {
        guard width > 0, height > 0, bytesPerRow >= width * MemoryLayout<Float>.stride else { return .measure([]) }
        let roiW = max(1, Int(Double(width) * 0.06)), roiH = max(1, Int(Double(height) * 0.06))
        let x0 = (width - roiW) / 2, y0 = (height - roiH) / 2
        var pixels: [Float] = []
        pixels.reserveCapacity(roiW * roiH)
        for y in y0..<(y0 + roiH) {
            let row = base.advanced(by: y * bytesPerRow).assumingMemoryBound(to: Float.self)
            for x in x0..<(x0 + roiW) { pixels.append(row[x]) }
        }
        return .measure(pixels)
    }
}

/// Inputs are DepthFloat32 meters, not disparity or display grayscale values.
struct PatchStatistics {
    let medianMeters: Double?
    let validFraction: Double
    let spatialSDMeters: Double?

    static func measure(_ pixels: [Float]) -> PatchStatistics {
        let valid = pixels.filter { $0.isFinite && $0 > 0 }.map(Double.init).sorted()
        let fraction = pixels.isEmpty ? 0 : Double(valid.count) / Double(pixels.count)
        guard !valid.isEmpty, fraction >= 0.6 else {
            return PatchStatistics(medianMeters: nil, validFraction: fraction, spatialSDMeters: nil)
        }
        let middle = valid.count / 2
        let median = valid.count.isMultiple(of: 2) ? (valid[middle - 1] + valid[middle]) / 2 : valid[middle]
        let mean = valid.reduce(0, +) / Double(valid.count)
        let sd = sqrt(valid.reduce(0) { $0 + pow($1 - mean, 2) } / Double(valid.count))
        return PatchStatistics(medianMeters: median, validFraction: fraction, spatialSDMeters: sd)
    }
}

struct DepthWindow {
    let capacity: Int
    private var values: [Double] = []
    private var previousTimestamp: Double?

    init(capacity: Int) { self.capacity = max(2, capacity) }

    var standardDeviation: Double? {
        guard values.count >= 2 else { return nil }
        let mean = values.reduce(0, +) / Double(values.count)
        return sqrt(values.reduce(0) { $0 + pow($1 - mean, 2) } / Double(values.count))
    }

    mutating func update(meters: Double?, timestamp: Double) -> Double? {
        if let previous = previousTimestamp, timestamp - previous > 0.5 || timestamp <= previous {
            values.removeAll()
        }
        previousTimestamp = timestamp
        guard let value = meters, value.isFinite, value > 0 else {
            values.removeAll()
            return nil
        }
        values.append(value)
        if values.count > max(2, capacity) { values.removeFirst() }
        return standardDeviation
    }
}

struct DepthRow {
    let elapsedSeconds: Double
    let meters: Double?
    let validFraction: Double
    let spatialSDMeters: Double?
    let temporalSDMeters: Double?
    var accuracy: String = "unknown"
}

enum DepthCSV {
    static func render(rows: [DepthRow], camera: String, cameraID: String,
                       phoneModel: String, systemVersion: String, referenceCM: Double?) -> String {
        func escape(_ value: String) -> String { "\"" + value.replacingOccurrences(of: "\"", with: "\"\"") + "\"" }
        func number(_ value: Double?) -> String {
            guard let value = value, value.isFinite else { return "" }
            return String(format: "%.6f", locale: Locale(identifier: "en_US_POSIX"), value)
        }
        let reference = referenceCM.flatMap { $0.isFinite && $0 > 0 ? $0 : nil }
        var lines = ["elapsed_s,depth_m,valid_fraction,spatial_sd_m,temporal_sd_m,reference_cm,error_cm,camera,camera_id,phone_model,ios_version,depth_filtering,roi_fraction,reported_accuracy"]
        for row in rows {
            let error: Double? = row.meters.flatMap { meters in reference.map { meters * 100 - $0 } }
            lines.append([number(row.elapsedSeconds), number(row.meters), number(row.validFraction),
                          number(row.spatialSDMeters), number(row.temporalSDMeters), number(reference),
                          number(error), escape(camera), escape(cameraID), escape(phoneModel),
                          escape(systemVersion), "false", "0.06", escape(row.accuracy)].joined(separator: ","))
        }
        return lines.joined(separator: "\n") + "\n"
    }
}
