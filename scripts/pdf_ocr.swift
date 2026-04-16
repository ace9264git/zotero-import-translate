#!/usr/bin/env swift

import AppKit
import Foundation
import PDFKit
import Vision

struct Options {
    var pdfPath: String = ""
    var maxPages: Int?
    var languages: [String] = ["en-US", "zh-Hans"]
}

enum OCRScriptError: Error {
    case invalidArguments(String)
    case openFailed(String)
    case renderFailed(Int)
}

func parseArgs() throws -> Options {
    var options = Options()
    let args = Array(CommandLine.arguments.dropFirst())
    var index = 0

    while index < args.count {
        let arg = args[index]
        switch arg {
        case "--pdf":
            index += 1
            guard index < args.count else {
                throw OCRScriptError.invalidArguments("Missing value for --pdf")
            }
            options.pdfPath = args[index]
        case "--max-pages":
            index += 1
            guard index < args.count, let pages = Int(args[index]), pages > 0 else {
                throw OCRScriptError.invalidArguments("Invalid value for --max-pages")
            }
            options.maxPages = pages
        case "--languages":
            index += 1
            guard index < args.count else {
                throw OCRScriptError.invalidArguments("Missing value for --languages")
            }
            options.languages = args[index].split(separator: ",").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
        default:
            throw OCRScriptError.invalidArguments("Unknown argument: \(arg)")
        }
        index += 1
    }

    if options.pdfPath.isEmpty {
        throw OCRScriptError.invalidArguments("Missing required --pdf argument")
    }
    return options
}

func renderPage(_ page: PDFPage, index: Int) throws -> CGImage {
    let bounds = page.bounds(for: .mediaBox)
    let targetSize = NSSize(
        width: max(bounds.width * 2.0, 1),
        height: max(bounds.height * 2.0, 1)
    )
    let thumbnail = page.thumbnail(of: targetSize, for: .mediaBox)
    guard let image = thumbnail.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        throw OCRScriptError.renderFailed(index)
    }
    return image
}

func recognizeText(from image: CGImage, languages: [String]) throws -> String {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = languages

    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])

    let observations = (request.results ?? []).sorted { lhs, rhs in
        let leftY = lhs.boundingBox.midY
        let rightY = rhs.boundingBox.midY
        if abs(leftY - rightY) > 0.02 {
            return leftY > rightY
        }
        return lhs.boundingBox.minX < rhs.boundingBox.minX
    }

    return observations.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
}

do {
    let options = try parseArgs()
    let url = URL(fileURLWithPath: options.pdfPath)
    guard let document = PDFDocument(url: url) else {
        throw OCRScriptError.openFailed("Unable to open PDF: \(options.pdfPath)")
    }

    let pageCount = document.pageCount
    let limit = min(options.maxPages ?? pageCount, pageCount)
    var pageOutputs: [String] = []
    pageOutputs.reserveCapacity(limit)

    for index in 0..<limit {
        guard let page = document.page(at: index) else { continue }
        let image = try renderPage(page, index: index + 1)
        let text = try recognizeText(from: image, languages: options.languages).trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.isEmpty {
            pageOutputs.append(text)
        }
    }

    let output = pageOutputs.joined(separator: "\n\n")
    FileHandle.standardOutput.write(output.data(using: .utf8) ?? Data())
} catch OCRScriptError.invalidArguments(let message) {
    FileHandle.standardError.write("ERROR: \(message)\n".data(using: .utf8) ?? Data())
    exit(2)
} catch OCRScriptError.openFailed(let message) {
    FileHandle.standardError.write("ERROR: \(message)\n".data(using: .utf8) ?? Data())
    exit(3)
} catch OCRScriptError.renderFailed(let page) {
    FileHandle.standardError.write("ERROR: Failed to render PDF page \(page)\n".data(using: .utf8) ?? Data())
    exit(4)
} catch {
    FileHandle.standardError.write("ERROR: \(error)\n".data(using: .utf8) ?? Data())
    exit(1)
}
