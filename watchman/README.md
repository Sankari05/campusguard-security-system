# 🛡️ CampusGuard: Smart Watchman & Campus Access Control System

A complete fullstack solution built with **React**, **Axios**, **Java 21 (Spring Boot)**, and **PostgreSQL** specifically engineered to eliminate watchman manual fatigue, automate student gate entries, and secure the campus.

---

## 🌟 How This Solves The Watchman's Pain Points

| Watchman Pain Point (கஷ்டங்கள்) | CampusGuard Solution (நம்ம தீர்வு) |
|---|---|
| 📝 **Manual Logbook Writing** (நோட்டுப் புத்தகத்தில் எழுதுவது) | **Fast Roll-No Lookup**: Watchman types or clicks student roll number (e.g. `22CS101`). Full photo, department, hostel, and parent contact load instantly with 1-click **IN (உள்ளே)** and **OUT (வெளியே)** buttons. |
| 📞 **Calling HOD/Warden for Permission** (போன் போட்டு அனுமதி கேட்பது) | **Digital Out-Pass Verification**: Students apply in-app; HOD 1-click approves; Guard verifies digital code (e.g. `OP-4592`) in 2 seconds. |
| 📦 **Messy Delivery & Lost Parcels** (பார்சல் குழப்பம்) | **Gate Parcel Desk with OTP Handover**: Log package from Amazon/Flipkart with recipient name; system verifies a 4-digit pickup OTP before handover so parcels never get lost. |
| 🗣️ **Language & Tech Barriers** (ஆங்கிலம் புரியாத நிலை) | **Bilingual Tamil & English Support**: Dedicated language toggle (`தமிழ்` / `English`) with Tamil voice announcements for guard actions. |
| 🚨 **Night Duty Emergency / Safety** (அவசர ஆபத்து) | **1-Click SOS Panic Broadcast**: Instantly broadcasts emergency alerts to campus supervisor, ambulance, and principal with siren sound. |
| 🏢 **Multi-Situation Versatility** | Modular architecture built to support **Colleges**, **Schools**, **Gated Apartments**, **Corporate IT Parks**, and **Jewellery Shops**. |

---

## 🚀 How to Run

### Frontend (React + Axios):
```bash
cd frontend
npm run dev
```
Open **http://localhost:5174/** in your browser.

### Backend (Java 21 + Spring Boot + PostgreSQL):
```bash
cd backend
mvn spring-boot:run
```
PostgreSQL schema is located in `backend/src/main/resources/schema.sql`.
