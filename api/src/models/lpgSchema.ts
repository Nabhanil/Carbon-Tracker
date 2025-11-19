import mongoose from "mongoose";

const lpgSchema = new mongoose.Schema({
  userId: { type: String, required: true },

  consumerNumber: String,
  provider: String,
  state: String,
  district: String,
  connectionType: String,
  subsidyStatus: String,

  cylindersConsumed: Number,
  lpgInKg: Number,
  carbonEmitted: Number,

  notes: String,
  createdAt: { type: Date, default: Date.now }
});

export default mongoose.model("LPGRecord", lpgSchema);
