# Gavi Technologies: 4 Core Products — Terminal Execution Manual
## முழுமையான தயாரிப்பு இயக்க கையேடு (Manual Terminal Run Guide)

இந்த ஆவணம் உங்கள் திட்ட கோப்பகத்தில் உள்ள **4 முதன்மை தயாரிப்புகள் (4 Core Products)** மற்றும் **ஒருங்கிணைந்த எண்டர்பிரைஸ் போர்டல் (Enterprise Portal)**-ஐ எவ்வாறு டெர்மினல் கட்டளைகள் (Terminal Commands) மூலம் தனித்தனியாகவும், இணைத்தும் இயக்குவது என்பதை விளக்குகிறது.

---

## 📌 விரைவு அட்டவணை (Quick Port & Access Map)

| # | தயாரிப்பு பெயர் (Product) | அடைவு (Directory) | Backend Port | Frontend Port | உலாவியில் பார்க்க (Browser URL) |
|---|---|---|---|---|---|
| **1** | **GuardMate (SmartWatchman AI)** | `watchman/` | `8080` | `5173` | [http://localhost:5173/](http://localhost:5173/) |
| **2** | **AI Face Recognition Attendance (EduTrack Pro)** | `smf_merged_fixed_updated/` | `8000` | `8000` (Unified) | [http://localhost:8000/](http://localhost:8000/) |
| **3** | **RidgeWatch (Survivor Detection System)** | `survivor-detection-system-main/` | `8002` | `8081` | [http://localhost:8081/](http://localhost:8081/) |
| **4** | **Android SMS Gateway** | `android-sms-gateway-master/` | Android App | Webhook (8080) | Android Device / Emulator |
| **★** | **Gavi Tech Enterprise Central Portal** | `enterprise_portal/` | - | `3000` | [http://localhost:3000/](http://localhost:3000/) |

---

## 🛡️ Product 1: GuardMate (SmartWatchman AI)
**பயன்பாடு:** கேம்பஸ் வாட்ச்மேன் மற்றும் பாதுகாப்பு பணிகளை டிஜிட்டல் மயமாக்கும் Cognitive AI Guard Co-Pilot தளம்.

### Terminal 1A — Backend இயக்குதல் (FastAPI):
```powershell
cd "c:\Users\sugan\OneDrive\Documents\3rd year project facevrecognization system\watchman\backend_python"
python run.py
```
* **வெளியீடு:** `http://localhost:8080`
* **Swagger API ஆவணங்கள்:** [http://localhost:8080/api/docs](http://localhost:8080/api/docs)

### Terminal 1B — Frontend இயக்குதல் (React + Vite):
```powershell
cd "c:\Users\sugan\OneDrive\Documents\3rd year project facevrecognization system\watchman\frontend"
cmd /c "npm run dev"
```
* **வாட்ச்மேன் கேட் கியோஸ்க்:** [http://localhost:5173/](http://localhost:5173/)
  * *Username:* `watchman1` | *Password:* `password123`
* **நிர்வாக தளம் (Admin Dashboard):** [http://localhost:5173/admin](http://localhost:5173/admin)
  * *Username:* `admin` | *Password:* `password123`
* **பார்வையாளர் செல்ஃப்-பாஸ் தளம்:** [http://localhost:5173/self-pass](http://localhost:5173/self-pass)

### தானியங்கி சோதனைகளை (Playwright E2E) இயக்க:
```powershell
cd "c:\Users\sugan\OneDrive\Documents\3rd year project facevrecognization system\watchman\frontend"
cmd /c "npx playwright test --project=chromium --workers=1"
```

---

## 👤 Product 2: AI Face Recognition Attendance (EduTrack Pro - SMF)
**பயன்பாடு:** ArcFace / LBPH Deep Learning மூலம் முக அங்கீகாரம், இரட்டையர்கள் (Twin) கண்டறிதல் மற்றும் வருகைப் பதிவு.

### முறை A: Web Portals & REST API இயக்குதல் (FastAPI):
```powershell
cd "c:\Users\sugan\OneDrive\Documents\3rd year project facevrecognization system\smf_merged_fixed_updated"
python api.py
```
* **ஒருங்கிணைந்த நுழைவு தளம் (Unified Gateway):** [http://localhost:8000/](http://localhost:8000/)
* **Admin Portal:** [http://localhost:8000/admin](http://localhost:8000/admin)
* **HOD Portal:** [http://localhost:8000/hod](http://localhost:8000/hod)
* **Faculty Portal:** [http://localhost:8000/faculty](http://localhost:8000/faculty)
* **Student Portal:** [http://localhost:8000/student](http://localhost:8000/student)
* *Admin Credentials:* Username: `admin` | Password: `password123` (or `.env` configuration)

### முறை B: Interactive Console Menu இயக்குதல் (Live Camera Session / Enrollment):
```powershell
cd "c:\Users\sugan\OneDrive\Documents\3rd year project facevrecognization system\smf_merged_fixed_updated"
python main.py
```
* **மெனு தேர்வுகள்:**
  * `[1]` — புதிய மாணவர்/ஆசிரியர் முகத்தை கேமராவில் Enroll செய்தல்
  * `[2]` — மாடலை Train செய்தல் (ArcFace / LBPH)
  * `[3]` — Live Camera வருகைப் பதிவு அமர்வு (Attendance Session)
  * `[4]` — Web API போர்ட்டலை தொடங்குதல்

---

## 📡 Product 3: RidgeWatch (Multi-Sensor Survivor Detection System)
**பயன்பாடு:** நிலச்சரிவு மற்றும் பேரிடர் பகுதிகளில் சிக்கியவர்களை மல்டி-சென்சார் மற்றும் ரேடார் மூலம் கண்டறிந்து மீட்பு பணிகளை வரிசைப்படுத்தும் அமைப்பு.

### Terminal 3A — Backend இயக்குதல் (FastAPI):
```powershell
cd "c:\Users\sugan\OneDrive\Documents\3rd year project facevrecognization system\survivor-detection-system-main\backend"
uvicorn api:app --host 0.0.0.0 --port 8002 --reload
```
* **Swagger API ஆவணங்கள்:** [http://localhost:8002/docs](http://localhost:8002/docs)

### Terminal 3B — Frontend UI இயக்குதல் (HTML5 Dashboard):
```powershell
cd "c:\Users\sugan\OneDrive\Documents\3rd year project facevrecognization system\survivor-detection-system-main\frontend"
python -m http.server 8081
```
* **கமாண்டர் கட்டுப்பாட்டு அறை (Incident Commander):** [http://localhost:8081/commander.html](http://localhost:8081/commander.html)
* **ரேடார் & டாப்ளர் காட்சி (Doppler Visualizer):** [http://localhost:8081/doppler.html](http://localhost:8081/doppler.html)
* **சென்சார் அனலிட்டிக்ஸ்:** [http://localhost:8081/analytics.html](http://localhost:8081/analytics.html)

---

## 📱 Product 4: Android SMS Gateway / Alert Dispatcher
**பயன்பாடு:** இணையம் இல்லாத அவசர காலங்களில் Android ஸ்மார்ட்போனை SMS Gateway-ஆக மாற்றி பெற்றோர் மற்றும் அதிகாரிகளுக்கு எச்சரிக்கை SMS அனுப்பும் தளம்.

### Android APK-வை உருவாக்க (Build Debug APK):
```powershell
cd "c:\Users\sugan\OneDrive\Documents\3rd year project facevrecognization system\android-sms-gateway-master"
.\gradlew.bat assembleDebug
```
* **APK கோப்பு சேமிக்கப்படும் இடம்:** `app\build\outputs\apk\debug\app-debug.apk`
* **பயன்படுத்தும் முறை:**
  1. உருவான APK-வை ஆண்ட்ராய்டு போனில் இன்ஸ்டால் செய்யவும்.
  2. ஆப்பில் காட்டும் IP முகவரி (எ.கா. `http://192.168.1.50:8080`) மூலம் பிற அமைப்புகள் SMS-களை அனுப்ப இயலும்.

---

## 🌐 Bonus: Gavi Technologies Enterprise Central Portal
**பயன்பாடு:** மேற்கண்ட அனைத்து 4 தயாரிப்புகளையும் ஒரே குடையின் கீழ் இணைக்கும் கார்ப்பரேட் எண்டர்பிரைஸ் தளம்.

### Terminal இயக்குதல்:
```powershell
cd "c:\Users\sugan\OneDrive\Documents\3rd year project facevrecognization system\enterprise_portal"
cmd /c "npm run dev -- --port 3000 --host"
```
* **சென்ட்ரல் போர்டல் URL:** [http://localhost:3000/](http://localhost:3000/)

---

## 🌐 CampusGuard (Port 5173) — முழுமையான URL Route & Module வழிகாட்டி (Complete URL Routing Map)

பிரவுசரில் (`http://localhost:5173/`) நேரடியாக எந்தவொரு குறிப்பிட்ட மாட்யூலுக்குள் செல்ல வேண்டுமானாலும் கீழ்க்கண்ட நேரடி URL Path-களை பயன்படுத்தலாம்:

### 1. பொது & சுய சேவை போர்ட்டல்கள் (Public & Self-Service Gateways)
| URL Path / Direct Link | Module Name (மாட்யூலின் பெயர்) | அணுகல் முறை (Access Role) | பயன்பாடு (Functionality) |
| :--- | :--- | :--- | :--- |
| [http://localhost:5173/](http://localhost:5173/) | **GuardMate SaaS Landing Page** | Public (யாருக்கும் அனுமதி) | தயாரிப்பு மேலோட்டம், 6 தொழில்துறை தேர்வு (College, Hospital, IT Park, Apartment, Factory, Event), வாடிக்கையாளர் பதிவு படிவம் |
| [http://localhost:5173/login](http://localhost:5173/login) | **Dedicated Login Portal** | All Users | வாட்ச்மேன் & அட்மின் உள்நுழைவு தளம் |
| [http://localhost:5173/self-pass](http://localhost:5173/self-pass) (அல்லது `/gate-qr`) | **Visitor & Student Gate QR Pass** | Public / Mobile Visitors | பார்வையாளர்கள் மற்றும் மாணவர்கள் மொபைலில் இருந்து டிஜிட்டல் கேட் பாஸ் பெறும் தளம் |

### 2. நிர்வாக தளங்கள் (Enterprise & Administration Portals)
| URL Path / Direct Link | Module Name (மாட்யூலின் பெயர்) | அணுகல் முறை (Access Role) | பயன்பாடு (Functionality) |
| :--- | :--- | :--- | :--- |
| [http://localhost:5173/super-admin](http://localhost:5173/super-admin) | **GuardMate SaaS Super Admin Console** | `SUPER_ADMIN` | நிறுவனங்களின் மேலாண்மை, சந்தா (SaaS Subscription) தணிக்கை, புதிய வளாகங்களை இணைத்தல் |
| [http://localhost:5173/tenant](http://localhost:5173/tenant) | **Tenant Organization Admin Portal** | `ORG_ADMIN` / `ADMIN` | நிறுவன பிரத்தியேக பாதுகாப்பு விதிமுறைகள் மற்றும் வாட்ச்மேன் அமைப்புகள் |
| [http://localhost:5173/admin](http://localhost:5173/admin) | **College Admin Executive Governance** | `ADMIN` / கல்லூரி முதல்வர் | கேட் பாதுகாப்பு நேரடி தணிக்கை, நெறிமுறை கண்காணிப்பு |
| [http://localhost:5173/admin#admin-compliance](http://localhost:5173/admin#admin-compliance) | **Late Arrivals Discipline (24h)** | `ADMIN` | தாமதமாக வந்த மாணவர்களின் துறைவாரியான அறிக்கை & எச்சரிக்கை |
| [http://localhost:5173/admin#admin-overdues](http://localhost:5173/admin#admin-overdues) | **Curfew Overdues & Violations** | `ADMIN` | விடுதி நேரத்தை தாண்டி வராத மாணவர்களின் விவரம் & பெற்றோர் SMS |
| [http://localhost:5173/admin#admin-shifts](http://localhost:5173/admin#admin-shifts) | **Shift Governance & Digital Sign-Off** | `ADMIN` | வாட்ச்மேன் ஷிப்ட் ஒப்படைப்பு தணிக்கை & கையெழுத்து |

### 3. வாட்ச்மேன் பாதுகாப்பு பணிகள் (Watchman Security Operations - 14 Live Pillars)
வாட்ச்மேன் உள்நுழைந்த பிறகு (Credentials: `watchman1` / `pass123`), நேரடியாக அந்தந்த மாட்யூலுக்கு செல்ல:

| URL Path / Direct Link | மாற்று வழிகள் (Path Aliases) | Module Name (மாட்யூலின் பெயர்) | பயன்பாடு (Key Features) |
| :--- | :--- | :--- | :--- |
| [http://localhost:5173/#copilot](http://localhost:5173/#copilot) | `/copilot` \| `/smartguard` | **AI Guard Co-Pilot (கார்டு கோ-பைலட்)** | லைவ் ரேடார் (Threat Radar), வாய்ஸ் இன்சிடென்ட் லாக் (Voice NLP Incident Logger), பாதுகாப்பு எச்சரிக்கைகள் |
| [http://localhost:5173/#parking](http://localhost:5173/#parking) | `/parking` \| `/smart-parking` | **Smart Campus Parking (பார்க்கிங் மேலாண்மை)** | 10 ஸ்லாட் விசுவல் வரைபடம், EV சார்ஜிங் ஸ்லாட்டுகள், இருசக்கர வாகன இடங்கள், அத்துமீறிய வாகன எச்சரிக்கை சைரன் (Review Alert) |
| [http://localhost:5173/#vehicles](http://localhost:5173/#vehicles) | `/vehicles` \| `/anpr` | **Vehicle Parking & ANPR Log (வாகன கேட் லாக்)** | கேமரா நம்பர் பிளேட் ஸ்கேனிங் (ANPR), வாகன உள்/வெளி பதிவுகள், அதிக நேரம் தங்கிய வாகனங்கள் |
| [http://localhost:5173/#visitors](http://localhost:5173/#visitors) | `/visitors` \| `/visitor-pass` | **Visitor Pass Desk (பார்வையாளர்கள் தளம்)** | உடனடி டிஜிட்டல் பாஸ், OTP சரிபார்ப்பு, விசிட்டர் பேட்ஜ் பிரிண்டிங் |
| [http://localhost:5173/#patrol](http://localhost:5173/#patrol) | `/patrol` \| `/checkpoints` | **Patrol Checkpoints (ரோந்து & QR சரிபார்ப்பு)** | வளாக பாதுகாப்பு ரோந்து வழிகள், QR செக்பாயிண்ட் ஸ்கேனிங் |
| [http://localhost:5173/#maintenance](http://localhost:5173/#maintenance) | `/maintenance` \| `/defects` | **Maintenance Defect (பராமரிப்பு பழுதுகள்)** | உடைந்த விளக்குகள், பழுதடைந்த தடுப்புகள், கேட் மோட்டார் புகார்கள் பதிவு & டிக்கெட் |
| [http://localhost:5173/#lost-found](http://localhost:5173/#lost-found) | `/lost-found` | **Lost & Found AI Match (தொலைந்தவை & கிடைத்தவை)** | தொலைந்த பொருட்கள் பதிவு, AI தானியங்கி பொருத்த சோதனைகள் (AI Matching Desk) |
| [http://localhost:5173/#zone-risk](http://localhost:5173/#zone-risk) | `/zone-risk` \| `/weather` | **Zone Risk & Weather (வானிலை & மண்டல ஆபத்து)** | மின்னல், கனமழை, வளாக வெள்ள அபாயம் மற்றும் வெயில் பாதுகாப்பு எச்சரிக்கைகள் |
| [http://localhost:5173/#duty](http://localhost:5173/#duty) | `/duty` \| `/attendance` | **Duty Attendance (பணி வருகை & லாக்)** | வாட்ச்மேன் பயோமெட்ரிக் வருகை, கேட் பணி ஒதுக்கீடு, நேரடி வருகை பதிவு |
| [http://localhost:5173/#handover](http://localhost:5173/#handover) | `/handover` \| `/shift-handover` | **Shift Handover (ஷிப்ட் ஒப்படைப்பு நெறிமுறை)** | வாக்கி-டாக்கி, சாவி ஒப்படைப்பு சரிபார்ப்பு, இரட்டை காவலர் கையொப்பம் |
| [http://localhost:5173/#parcels](http://localhost:5173/#parcels) | `/parcels` \| `/courier` | **Parcel Desk (பார்சல்கள் & கூரியர் மேலாண்மை)** | அமேசான்/பிளிப்கார்ட் பார்சல் லாக், OTP சரிபார்த்து விநியோகித்தல் |
| [http://localhost:5173/#emergency](http://localhost:5173/#emergency) | `/emergency` \| `/sos` | **Emergency SOS Hub (அவசர உதவி SOS)** | ஒரே தொடுதலில் கேட் லாக்டவுன், ஆம்புலன்ஸ், தீயணைப்பு மற்றும் போலீஸ் உடனடி அலர்ட் |
| [http://localhost:5173/#dashboard](http://localhost:5173/#dashboard) | `/dashboard` \| `/analytics` | **Gate Analytics (கேட் மேலோட்டம் & பகுப்பாய்வு)** | நேரடி கேட் நெரிசல் வரைபடம், மாணவர்கள்/வாகனங்கள் புள்ளிவிவரம் |
| [http://localhost:5173/#guardmate-workspace](http://localhost:5173/#guardmate-workspace) | `/workspace` | **GuardMate Facility OS (பிரத்யேக தளம்)** | மல்டி-டெனன்ட் இடைமுகம், பல்வேறு தொழில்துறைக்கு ஏற்ப மாறும் கேட் கருவிகள் |
| [http://localhost:5173/#gate-kiosk](http://localhost:5173/#gate-kiosk) | `/gate-kiosk` \| `/gate` | **Gate Ingress/Egress Kiosk (மெயின் கேட் Kiosk)** | விரைவான மாணவர் ஐடி கார்டு ஸ்கேனிங் & தானியங்கி தடுப்புத் திறப்பு |
| [http://localhost:5173/#out-pass](http://localhost:5173/#out-pass) | `/out-pass` \| `/outpass` | **Student Out-Pass (மாணவர் அவுட்பாஸ் மேலாண்மை)** | வார்டன் / HOD அனுமதித்த அவுட்பாஸ் சரிபார்த்து கேட் வெளியேற்றம் பதிவு செய்தல் |


