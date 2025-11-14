import mongoose from "mongoose";

const extractedInvoiceSchema = new mongoose.Schema({
  fileId: { type: mongoose.Schema.Types.ObjectId, ref: "Pdf", required: true },
  fileName: { type: String, required: true },
  vendor: {
    name: String,
    address: String,
    taxId: String
  },
  invoice: {
    number: String,
    date: String,
    currency: String,
    subtotal: Number,
    taxPercent: Number,
    total: Number,
    poNumber: String,
    poDate: String,
    lineItems: [
      {
        description: String,
        unitPrice: Number,
        quantity: Number,
        total: Number
      }
    ]
  },
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date }
});

const ExtractedInvoice = mongoose.model("ExtractedInvoice", extractedInvoiceSchema);

export default ExtractedInvoice;
