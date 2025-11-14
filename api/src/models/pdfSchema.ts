import mongoose from "mongoose";

const pdfSchema = new mongoose.Schema({
    fileName: { type: String, required: true },
    fileData: { type: Buffer, required: true },
    contentType: { type: String, default: "application/pdf" },
    uploadedAt: { type: Date, default: Date.now }
});

const PdfModel = mongoose.model("Pdf", pdfSchema);

export default PdfModel;
