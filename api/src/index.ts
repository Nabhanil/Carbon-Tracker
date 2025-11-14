import express from "express";
import mongoose from "mongoose";
import multer from "multer";
import "dotenv/config";
import { GoogleGenAI } from "@google/genai";
import { readFile } from 'node:fs/promises';
import { PDFParse } from 'pdf-parse';

import cors from "cors";
import BillModel from "./models/billSchema.js";

const app = express();
const ai = new GoogleGenAI({});
app.use(express.json());
app.use(cors({ origin: "*", methods: ["GET", "POST"] }));

// Multer setup: Accept both PDFs and Images
const storage = multer.memoryStorage();
const upload = multer({
  storage,
  limits: { fileSize: 25 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const allowed = [
      "application/pdf",
      "image/jpeg",
      "image/png",
      "image/jpg",
    ];
    if (allowed.includes(file.mimetype)) cb(null, true);
    else cb(new Error("Only PDF, JPG, PNG allowed"));
  },
});

// Utility: Calculate CO₂ emissions
const calcCarbon = (units: any) => (units * 0.82).toFixed(2);

// 📍 Upload Route
app.post("/upload-bill", upload.single("bill"), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: "No file uploaded" });

    let extractedText = "";
    if (req.file.mimetype === "application/pdf") {
      const dataBuffer = req.file.buffer;
      // const buffer = await readFile('reports/pdf/climate.pdf');
      const parser = new PDFParse({ data: dataBuffer });
      // directly use buffer from multer
      const result = await parser.getText(); // or pdf(dataBuffer) if using ES module syntax
      //@ts-ignore
      extractedText = result.text || "";
    }
    else {
      // For images (future extension: OCR via Gemini or Tesseract)
      const aiResponse = await ai.models.generateContent({
        model: "gemini-2.0-flash",
        contents: [
          {
            role: "user",
            parts: [{ inlineData: { mimeType: req.file.mimetype, data: req.file.buffer.toString("base64") } }],
          },
          {
            role: "user",
            parts: [{ text: "Extract all text content from this electricity bill image." }],
          },
        ],
      });
      extractedText = aiResponse.text as string;
    }

    // Structure extraction prompt
    const structuredResponse = await ai.models.generateContent({
      model: "gemini-2.0-flash",
      contents: [
        {
          role: "user",
          parts: [
            {
              text: `
Extract this text into JSON:
{
  "consumerName": "",
  "billNumber": "",
  "billingDate": "",
  "billingMonth": "",
  "unitsConsumed": 0,
  "totalAmount": 0,
  "address": "",
  "tariffType": ""
}
Here is the text:
${extractedText}`,
            },
          ],
        },
      ],
    });

    let structuredData;
    try {
      console.log("Structured Response:", structuredResponse);
      const rawText = structuredResponse?.text ?? "";
      if (!rawText.trim()) {
        return res.status(500).json({ error: "AI returned no JSON text" });
      }
      structuredData = JSON.parse(rawText.replace(/```json|```/g, "").trim());
    } catch (e) {
      return res.status(500).json({ error: "AI returned invalid JSON" });
    }

    // Calculate emissions
    const carbonEmitted = calcCarbon(structuredData.unitsConsumed);

    // Save to MongoDB
    const newBill = new BillModel({
      fileName: req.file.originalname,
      fileType: req.file.mimetype,
      billData: req.file.buffer,
      extracted: structuredData,
      carbonEmitted,
      uploadedAt: new Date(),
    });

    await newBill.save();

    res.status(200).json({
      success: true,
      message: "Bill processed successfully",
      data: { ...structuredData, carbonEmitted },
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to process bill" });
  }
});

// 📊 Daily & Monthly Tracking
app.get("/emissions-summary", async (req, res) => {
  try {
    const bills = await BillModel.find();
    const monthly: Record<string, number> = {};
    let total = 0;

    bills.forEach((bill) => {
      const month = String(bill.extracted?.billingMonth || "Unknown");
      const emitted = parseFloat(String(bill.carbonEmitted)) || 0;
      monthly[month] = (monthly[month] || 0) + emitted;
      total += emitted;
    });

    res.json({ total, monthly });
  } catch (err) {
    res.status(500).json({ error: "Failed to fetch summary" });
  }
});

// 🧠 AI-based insights (optional)
app.get("/carbon-insights", async (req, res) => {
  try {
    const bills = await BillModel.find().sort({ uploadedAt: -1 }).limit(5);
    const usageData = bills.map(
      (b) => `${b.extracted?.billingMonth ?? "Unknown"}: ${b.carbonEmitted ?? 0} kg CO₂`
    );

    const prompt = `
Analyze the following monthly carbon usage:
${usageData.join("\n")}
Give short insights and 3 actionable suggestions to reduce electricity-based emissions.`;

    const aiResponse = await ai.models.generateContent({
      model: "gemini-2.0-flash",
      contents: [{ role: "user", parts: [{ text: prompt }] }],
    });

    res.json({ insights: aiResponse.text });
  } catch (err) {
    res.status(500).json({ error: "Failed to generate insights" });
  }
});

// 📍Fetch details from consumer number
app.post("/fetch-bill", async (req, res) => {

});


// DB connection
const mongoUri = process.env.MONGO_URI;
if (!mongoUri) {
  console.error("MONGO_URI environment variable is not set. Exiting.");
  process.exit(1);
}

mongoose
  .connect(mongoUri, { dbName: "carbonwise" })
  .then(() => {
    app.listen(process.env.PORT || 3000, () =>
      console.log("✅ Server running...")
    );
  })
  .catch((e) => console.error("DB connection failed:", e));

export default app;
