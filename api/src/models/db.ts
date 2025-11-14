// db.js
import mongoose from "mongoose";
//@ts-ignore
let cached = global.mongoose;
//@ts-ignore
if (!cached) cached = global.mongoose = { conn: null, promise: null };

export default async function connectToDatabase() {
  if (cached.conn) return cached.conn;
  if (!cached.promise) {
    cached.promise = mongoose.connect(process.env.MONGO_URI as string, {
      dbName: "flowbitai",
    }).then((mongoose) => mongoose);
  }
  cached.conn = await cached.promise;
  return cached.conn;
}
