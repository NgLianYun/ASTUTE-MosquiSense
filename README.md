# MosquiSense — AI-Based Mosquito Monitoring System

MosquiSense is a proposed solar-powered mosquito capture, detect and monitoring product for public spaces. Its current **software prototype** combines a Roboflow mosquito detection workflow, a Python backend, a Supabase database and an interactive HTML dashboard.

## How the system works

**Sample mosquito image → Roboflow AI → Python backend → Supabase `live_data` → HTML dashboard**

1. A sample photo is placed manually in `backend/input/Q-001.jpg`.
2. The Roboflow model identifies mosquitoes in the photo and returns a detection count.
3. `mosquisense_worker.py` updates the **Q-001** record in the Supabase `public.live_data` table.
4. The dashboard in `index.html` reads the latest station data directly from Supabase and displays mosquito counts, station details, map markers and activity rankings.

### Live dashboard updates

The dashboard is built with **HTML, CSS and JavaScript** and connected to Supabase. When a station's `mosquito_count` changes in `live_data`, the dashboard can refresh **without manually reloading the web page**:

- **Supabase Realtime** listens for database changes.
- A **30-second polling fallback** periodically requests the latest readings if a Realtime event is missed or unavailable.
- The dashboard refreshes displayed counts, activity categories and rankings from the latest received values.

**Realtime means that the webpage reacts to database updates; it does not mean the camera captures images automatically.** In the current prototype, the user manually provides an image and runs the Python worker. Only **Q-001** has been tested with the Roboflow-to-Supabase pipeline; other station readings are demonstration data.

## Project files

```text
MosquiSense/
├── index.html                 # HTML monitoring dashboard
├── map-data.js                # Map data
├── backend/
│   ├── mosquisense_worker.py  # Roboflow detection → Supabase update
│   ├── test_roboflow.py       # Detection test and annotated image
│   ├── app.py                 # Flask detection API
│   ├── requirements.txt
│   ├── .env.example           # Configuration template
│   └── input/Q-001.jpg        # Manually provided sample image
├── supabase/schema.sql        # Fresh-project database setup
├── download_small_osm.py     # Map data download utility
├── build_geofabrik.py        # Map data processing utility
└── README.md
```

## Run the prototype

**1. Install backend dependencies**

```bash
cd backend
pip install -r requirements.txt
```

**2. Configure `backend/.env`** using the values required by your Supabase project and Roboflow workflow:

```dotenv
ROBOFLOW_API_KEY=YOUR_ROBOFLOW_API_KEY
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
```

The Supabase database must already have the `public.live_data` table and the `Q-001` record. `supabase/schema.sql` documents the fresh-project setup; **do not run its reset statements on a working database**.

**3. Detect mosquitoes and update Supabase**

Place your test image at `backend/input/Q-001.jpg`, then run:

```bash
python test_roboflow.py
python mosquisense_worker.py
```

The first command tests detection and creates an annotated image. The second updates the latest Q-001 count in Supabase.

**4. Open the HTML Dashboard**

Open `index.html` in a web browser to access the MosquiSense monitoring dashboard.

The dashboard connects directly to Supabase to retrieve the latest mosquito detection counts, temperature, humidity, and device information. Supabase Realtime enables the displayed information to update automatically whenever the database changes, with a 30-second refresh fallback.

An internet connection is required for Supabase connectivity. No physical mosquito killer or camera is required to demonstrate the dashboard.

## Prototype status and limitations

| Feature | Status |
|---|---|
| HTML monitoring dashboard connected to Supabase | Implemented |
| Supabase Realtime and 30-second refresh fallback | Implemented in frontend |
| Roboflow detection of a supplied photograph | Implemented |
| Python update of Q-001 in Supabase | Tested successfully |
| Automatic physical camera capture every five minutes | Not implemented |
| Physical mosquito killer | Concept design only |
| Multiple deployed mosquito-killer devices | Not implemented |

 Future development will integrate the physical camera, automated image capture, unique-counting logic and field testing.


