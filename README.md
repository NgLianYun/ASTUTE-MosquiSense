# MosquiSense — AI-Based Mosquito Monitoring System

MosquiSense is a smart mosquito monitoring prototype that integrates **Roboflow image detection, a Python backend, Supabase database, and an interactive HTML dashboard**.

The proposed product is a solar-powered mosquito killer designed to attract, capture, and monitor mosquitoes in public spaces.

## 1. System Overview

The current software prototype follows this workflow:

**Mosquito Image → Roboflow AI → Python Backend → Supabase → MosquiSense Dashboard**

A sample image is manually provided to the AI model. The detected mosquito count is sent to Supabase and displayed on the monitoring dashboard.

## 2. Project Structure

```text
MosquiSense/
├── index.html
├── map-data.js
├── backend/
│   ├── mosquisense_worker.py
│   ├── test_roboflow.py
│   ├── app.py
│   ├── requirements.txt
│   ├── .env.example
│   └── input/
│       └── Q-001.jpg
├── supabase/
├── download_small_osm.py
├── build_geofabrik.py
├── .gitignore
└── README.md
```

### Main Components

| File | Description |
|---|---|
| `index.html` | Interactive MosquiSense monitoring dashboard |
| `map-data.js` | Geographic data for the monitoring map |
| `backend/mosquisense_worker.py` | Detects mosquitoes and updates Supabase |
| `backend/test_roboflow.py` | Tests AI detection and generates bounding boxes |
| `backend/app.py` | Flask-based image detection API |
| `backend/requirements.txt` | Python dependencies |
| `supabase/` | Database setup and related SQL files |
| `download_small_osm.py` | Downloads OpenStreetMap data |
| `build_geofabrik.py` | Processes map data |

## 3. Technologies Used

- **Frontend:** HTML, CSS, JavaScript
- **Machine Learning:** Roboflow
- **Backend:** Python and Flask
- **Database:** Supabase PostgreSQL
- **Mapping:** OpenStreetMap
- **Version Control:** GitHub

## 4. Installation and Setup

### Install Python dependencies

Open a terminal in the project folder:

```bash
cd backend
pip install -r requirements.txt
```

### Configure environment variables

Create a `.env` file inside `backend/`:

```env
ROBOFLOW_API_KEY=YOUR_ROBOFLOW_API_KEY
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
```

The Supabase project must contain the `public.live_data` table and a record with `device_id = 'Q-001'`.

### Run AI Detection

Place a sample mosquito photograph at:

`backend/input/Q-001.jpg`

Run the detection test:

```bash
python test_roboflow.py
```

Run the AI-to-Supabase integration:

```bash
python mosquisense_worker.py --once
```

The detected mosquito count will update device **Q-001** in the Supabase `live_data` table.

### Open the Dashboard

From the main project folder:

```bash
python -m http.server 5500
```

Open `http://localhost:5500` in your browser.

An internet connection is required for Supabase.

## 5. Current Prototype Status

| Component | Status |
|---|---|
| Interactive monitoring dashboard | Implemented |
| Roboflow mosquito image detection | Implemented |
| Python–Supabase integration | Tested successfully |
| Q-001 database update | Working |
| Physical mosquito killer | Concept design |
| Automatic camera capture | Not implemented |
| Multiple physical devices | Not implemented |

**Note:** The current system detects mosquitoes in a manually supplied image. The detection count does not represent verified mosquito kills.

## 6. Future Development

Future improvements include integrating a physical camera, automatic image capture every five minutes, automated counting, and deployment of multiple mosquito-killer units.

## 7. Security

API credentials are stored in a local `.env` file, which must not be uploaded to GitHub.

The Supabase service-role key is used only by the Python backend. Website users access the database through read-only frontend permissions.

---

**MosquiSense — Academic Software Proof-of-Concept**
