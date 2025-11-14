import mongoose from "mongoose";

const billSchema = new mongoose.Schema({
  fileName: String,
  fileType: String,
  billData: Buffer,
  extracted: {
    consumerName: String,
    billNumber: String,
    billingDate: String,
    billingMonth: String,
    unitsConsumed: Number,
    totalAmount: Number,
    address: String,
    tariffType: String,
  },
  carbonEmitted: Number,
  uploadedAt: Date,
});

export default mongoose.model("ElectricityBill", billSchema);
