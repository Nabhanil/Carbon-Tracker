# Carbon Tracker API Documentation

This document provides a comprehensive guide to the Carbon Tracker API. The API is divided into three main services:

1.  **Diet CO2 Service**: For calculating CO2 emissions from food consumption.
2.  **VIN CO2 Service**: For calculating CO2 emissions from vehicles.
3.  **Billing Service**: For calculating CO2 emissions from electricity and LPG consumption.

---

## 1. Diet CO2 Service

This service provides an endpoint to calculate the CO2 emissions of a list of food items.

### POST `/compute_food_co2`

Calculates the CO2 emissions for a list of food items.

**Request Body:**

```json
{
  "user_id": "string",
  "items": [
    {
      "food_type": "string",
      "quantity_grams": "number"
    }
  ],
  "ate_at": "string"
}
```

**Parameters:**

| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `user_id` | string | The ID of the user. | Yes |
| `items` | array | A list of food items. | Yes |
| `food_type`| string | The name of the food item. | Yes |
| `quantity_grams`| number | The quantity of the food item in grams. | Yes |
| `ate_at` | string | The date and time the food was eaten (ISO 8601 format). | No |

**Example Success Response (200 OK):**

```json
{
  "session_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "user_id": "user123",
  "ate_at": "2025-11-19T12:00:00Z",
  "results": [
    {
      "food_type": "Rice",
      "quantity_grams": 200,
      "kgco2e_per_kg": 2.7,
      "co2_kg": 0.54
    }
  ],
  "total_co2_kg": 0.54
}
```

**Example Error Response (404 Not Found):**

```json
{
  "detail": "Emission factor not found for 'Unknown Food'. Please add to CSV or food_efs collection."
}
```

---

## 2. VIN CO2 Service

This service provides endpoints for managing vehicle information and calculating CO2 emissions from vehicle usage.

### GET `/`

A simple endpoint to check if the service is running.

**Example Response (200 OK):**

```json
{
  "Response": "You are at home"
}
```

### GET `/ping`

A health check endpoint.

**Example Response (200 OK):**

```json
{
  "status": "ok"
}
```

### POST `/upload-vin`

Uploads a VIN image, extracts the VIN, decodes it, and stores the vehicle information.

**Request Body:**

The request should be a `multipart/form-data` request containing the `user_id` and the `file` to be uploaded.

**Parameters:**

| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `user_id` | string | The ID of the user. | Yes |
| `file` | file | The VIN image file. | Yes |

**Example Success Response (200 OK):**

```json
{
  "vin": "1G1FY1EL2M123456",
  "decoded": {
    "Make": "CHEVROLET",
    "Model": "Bolt EV",
    "Model Year": "2022",
    "VehicleType": "PASSENGER CAR",
    "BodyClass": "Hatchback",
    "EngineCylinders": "0",
    "FuelTypePrimary": "Electric"
  },
  "vehicle_category": "CAR",
  "fuel_type": "ELECTRIC"
}
```

### POST `/calculate/daily`

Calculates the daily CO2 emissions for a user's vehicle based on GPS data.

**Request Body:**

```json
{
  "user_id": "string",
  "country_code": "string",
  "subregion": "string"
}
```

**Parameters:**

| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `user_id` | string | The ID of the user. | Yes |
| `country_code`| string | The user's country code. | No |
| `subregion` | string | The user's subregion. | No |

**Example Success Response (200 OK):**

```json
{
  "ok": true,
  "record": {
    "_id": "638d4b7f1a2b3c4d5e6f7a8b",
    "user_id": "user123",
    "date": "2025-11-19",
    "vehicle": {
      "vin": "1G1FY1EL2M123456",
      "vehicle_category": "CAR",
      "fuel_type": "ELECTRIC"
    },
    "distance_km": 50,
    "co2_kg_per_unit": 0.1,
    "total_kg_co2": 5,
    "details": {
      "co2_kg_per_unit": 0.1,
      "unit": "kWh"
    },
    "created_at": "2025-11-19T12:00:00Z"
  }
}
```

### POST `/gps/update`

Receives and stores GPS data (latitude, longitude, speed, etc.) for a user.

**Request Body:**

```json
{
  "user_id": "string",
  "lat": "number",
  "lon": "number",
  "speed_kmh": "number",
  "distance_km": "number",
  "timestamp_iso": "string"
}
```

**Parameters:**

| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `user_id` | string | The ID of the user. | Yes |
| `lat` | number | The latitude. | No |
| `lon` | number | The longitude. | No |
| `speed_kmh` | number | The speed in km/h. | No |
| `distance_km`| number | The distance in km. | No |
| `timestamp_iso`| string | The timestamp in ISO 8601 format. | No |

**Example Success Response (200 OK):**

```json
{
  "ok": true,
  "stored": {
    "user_id": "user123",
    "lat": 34.0522,
    "lon": -118.2437,
    "speed_kmh": 60,
    "distance_km": 1,
    "timestamp": "2025-11-19T12:00:00Z",
    "date": "2025-11-19",
    "_id": "638d4b7f1a2b3c4d5e6f7a8c"
  }
}
```

### GET `/gps/daily-modes`

Provides a summary of a user's daily activity, categorized by inferred transportation mode (walk, bike, car).

**Query Parameters:**

| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `user_id` | string | The ID of the user. | Yes |
| `day` | string | The date in `YYYY-MM-DD` format. | No |

**Example Success Response (200 OK):**

```json
{
  "ok": true,
  "user_id": "user123",
  "date": "2025-11-19",
  "total_km": 50,
  "by_mode": {
    "CAR": 45,
    "WALK": 5
  },
  "records_count": 100
}
```

### GET `/gps/daily-modes/export`

Exports the daily mode summary as a CSV file.

**Query Parameters:**

| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `user_id` | string | The ID of the user. | Yes |
| `day` | string | The date in `YYYY-MM-DD` format. | No |

**Example Response (200 OK):**

A CSV file will be downloaded.

### GET `/predict/mode`

Predicts the transport mode based on speed.

**Query Parameters:**

| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `speed` | number | The speed in km/h. | Yes |

**Example Response (200 OK):**

```json
{
  "speed_kmh": 80,
  "predicted_mode": "CAR (highway)"
}
```

---

## 3. Billing Service

This service provides endpoints for calculating CO2 emissions from electricity and LPG consumption.

### POST `/upload-bill`

Uploads an electricity bill (PDF or image), extracts the text, and calculates the carbon emissions.

**Request Body:**

The request should be a `multipart/form-data` request containing the `userId` and the `bill` file to be uploaded.

**Parameters:**

| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `userId` | string | The ID of the user. | Yes |
| `bill` | file | The bill file (PDF or image). | Yes |

**Example Success Response (200 OK):**

```json
{
  "success": true,
  "message": "Bill processed successfully",
  "data": {
    "consumerName": "John Doe",
    "billNumber": "123456789",
    "billingDate": "2025-11-01",
    "billingMonth": "October",
    "unitsConsumed": 200,
    "totalAmount": 1500,
    "address": "123 Main St, Anytown",
    "tariffType": "Residential",
    "carbonEmitted": 164
  }
}
```

### GET `/emissions-summary`

Retrieves a summary of all emissions data.

**Example Success Response (200 OK):**

```json
{
  "total": 500,
  "monthly": {
    "October": 200,
    "November": 300
  }
}
```

### GET `/carbon-insights`

Generates AI-based insights and suggestions for reducing emissions.

**Example Success Response (200 OK):**

```json
{
  "insights": "Your carbon emissions have increased by 50% in November. Here are some suggestions to reduce your emissions:\n1. ...\n2. ...\n3. ..."
}
```

### POST `/fetch-bill`

This endpoint is defined but not implemented.

### POST `/fetch-lpg`

Extracts LPG consumption details from text and calculates emissions.

**Request Body:**

```json
{
  "lpgText": "string",
  "userId": "string"
}
```

**Parameters:**

| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `lpgText` | string | The text containing LPG consumption details. | Yes |
| `userId` | string | The ID of the user. | Yes |

**Example Success Response (200 OK):**

```json
{
  "success": true,
  "message": "LPG data extracted & stored successfully.",
  "data": {
    "consumerNumber": "12345",
    "provider": "Gas Co",
    "state": "CA",
    "district": "Los Angeles",
    "month": "October",
    "connectionType": "Single",
    "subsidyStatus": "Yes",
    "cylindersConsumed": 1,
    "lpgInKg": 14.2,
    "notes": "",
    "carbonEmitted": 44.2
  }
}
```

### POST `/calculate-lpg-emissions`

Calculates LPG emissions based on the number of cylinders or kilograms consumed.

**Request Body:**

```json
{
  "cylindersConsumed": "number",
  "lpgInKg": "number"
}
```

**Parameters:**

| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `cylindersConsumed` | number | The number of cylinders consumed. | No |
| `lpgInKg` | number | The weight of LPG consumed in kg. | No |

**Example Success Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "cylindersConsumed": 1,
    "lpgInKg": 0,
    "carbonEmitted": 44.2
  }
}
```
