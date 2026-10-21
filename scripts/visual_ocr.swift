// OCR a screenshot with macOS Vision and print normalized text boxes.
//
//   swift scripts/visual_ocr.swift /tmp/fl-window.png
//
// Boxes are normalized to the image with the origin at the TOP-LEFT, which is
// convenient for converting to screen coordinates. This is a computer-use
// primitive: prefer OCR/AX targets over hard-coded pixel guesses.
import Foundation
import Vision
import ImageIO

guard CommandLine.arguments.count >= 2 else {
    fputs("usage: visual_ocr.swift <image>\n", stderr)
    exit(2)
}
let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
      let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
    fputs("cannot read image\n", stderr)
    exit(1)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["zh-Hans", "en-US"]

let handler = VNImageRequestHandler(cgImage: image, options: [:])
do {
    try handler.perform([request])
} catch {
    fputs("vision failed: \(error)\n", stderr)
    exit(1)
}

let observations = (request.results ?? []).sorted {
    let ay = 1.0 - $0.boundingBox.maxY
    let by = 1.0 - $1.boundingBox.maxY
    if abs(ay - by) > 0.01 { return ay < by }
    return $0.boundingBox.minX < $1.boundingBox.minX
}

var rows: [[String: Any]] = []
for observation in observations {
    guard let candidate = observation.topCandidates(1).first else { continue }
    let box = observation.boundingBox
    rows.append([
        "text": candidate.string,
        "confidence": candidate.confidence,
        "x": box.minX,
        "y": 1.0 - box.maxY,
        "w": box.width,
        "h": box.height,
    ])
}
let data = try JSONSerialization.data(withJSONObject: rows, options: [.prettyPrinted, .sortedKeys])
print(String(data: data, encoding: .utf8) ?? "[]")
