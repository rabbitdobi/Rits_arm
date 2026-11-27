import Foundation

var checks = 0
func check(_ condition: @autoclosure () -> Bool, _ message: String) {
    checks += 1
    guard condition() else { fatalError("FAIL: \(message)") }
}
func close(_ actual: Double?, _ expected: Double, _ message: String) {
    check(actual != nil && abs(actual! - expected) < 0.000001, message)
}

let normal = PatchStatistics.measure([0.39, 0.40, 0.41, .nan, 0])
close(normal.medianMeters, 0.40, "DepthFloat32 values remain meters")
close(normal.validFraction, 0.6, "Invalid pixels count toward coverage denominator")
check(PatchStatistics.measure([.nan, .infinity, -1, 0]).medianMeters == nil,
      "Nonfinite, zero and negative depths cannot become a measurement")
check(PatchStatistics.measure([0.4, .nan, .nan]).medianMeters == nil,
      "Sparse center patch is suppressed")
check(PatchStatistics.measure([]).validFraction == 0, "Empty patch has zero coverage")
close(PatchStatistics.measure([0.2, 0.4]).medianMeters, 0.3, "Even count median")

let padded: [Float] = [9, 9, 9, 99, 9, 0.4, 9, 99, 9, 9, 9, 99]
let patch = padded.withUnsafeBytes {
    CenterPatch.measure(base: $0.baseAddress!, width: 3, height: 3, bytesPerRow: 16)
}
close(patch.medianMeters, 0.4, "Center ROI honors row padding and excludes background")
let invalidStride = padded.withUnsafeBytes {
    CenterPatch.measure(base: $0.baseAddress!, width: 3, height: 3, bytesPerRow: 4)
}
check(invalidStride.medianMeters == nil, "Invalid buffer stride is rejected")

var window = DepthWindow(capacity: 3)
_ = window.update(meters: 0.3, timestamp: 0)
_ = window.update(meters: 0.4, timestamp: 0.1)
close(window.update(meters: 0.5, timestamp: 0.2), sqrt(0.02 / 3), "Temporal population SD")
_ = window.update(meters: 0.6, timestamp: 0.3)
close(window.standardDeviation, sqrt(0.02 / 3), "Sliding window discards oldest frame")
check(window.update(meters: nil, timestamp: 0.4) == nil, "Invalid frame clears stale window")
check(window.update(meters: 0.8, timestamp: 0.5) == nil, "One sample has no jitter estimate")
_ = window.update(meters: 0.9, timestamp: 0.6)
check(window.update(meters: 1, timestamp: 2) == nil, "Long gaps clear jitter history")

let rows = [DepthRow(elapsedSeconds: 0.1, meters: 0.42, validFraction: 0.8,
                     spatialSDMeters: 0.01, temporalSDMeters: 0.002),
            DepthRow(elapsedSeconds: 0.2, meters: nil, validFraction: 0.2,
                     spatialSDMeters: nil, temporalSDMeters: nil)]
let csv = DepthCSV.render(rows: rows, camera: "Rear, LiDAR", cameraID: "device\"id",
                          phoneModel: "iPhone17,2", systemVersion: "26.0", referenceCM: 40)
check(csv.contains("\"Rear, LiDAR\""), "CSV escapes commas")
check(csv.contains("\"device\"\"id\""), "CSV escapes quotes")
check(csv.contains("0.420000"), "CSV records meters")
check(csv.contains("2.000000"), "CSV records signed error in cm against measured reference")
check(csv.components(separatedBy: "\n").filter { !$0.isEmpty }.count == 3,
      "CSV has one header and every frame including invalid frames")
print("PASS: \(checks) depth statistics and CSV checks")
