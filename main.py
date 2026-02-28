from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, auth, db
from pydantic import BaseModel
from typing import Optional
import os
import json
from datetime import datetime

# ─── FIREBASE INIT ───────────────────────────────────────────────
# Supports both local (serviceAccountKey.json file) and Render (env variable)
def init_firebase():
    database_url = "https://summit-pt-clinic-default-rtdb.asia-southeast1.firebasedatabase.app"
    
    # Option 1: Environment variable (for Render/Railway)
    firebase_credentials = os.environ.get("FIREBASE_CREDENTIALS")
    if firebase_credentials:
        try:
            # Clean up common pasting issues
            cred_dict = json.loads(firebase_credentials)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {"databaseURL": database_url})
            print("✅ Firebase initialized from environment variable")
            return
        except json.JSONDecodeError as e:
            print(f"❌ FIREBASE_CREDENTIALS JSON parse error: {e}")
            print("Make sure you copied the ENTIRE serviceAccountKey.json content")
            raise

    # Option 2: Local file (for development)
    key_path = "serviceAccountKey.json"
    if os.path.exists(key_path):
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred, {"databaseURL": database_url})
        print("✅ Firebase initialized from serviceAccountKey.json file")
        return

    raise RuntimeError(
        "No Firebase credentials found!\n"
        "- For local: add serviceAccountKey.json to this folder\n"
        "- For Render: add FIREBASE_CREDENTIALS environment variable"
    )

init_firebase()

# ─── FASTAPI APP ─────────────────────────────────────────────────
app = FastAPI(
    title="Summit PT Clinic API",
    description="Time, Attendance, and Payroll Management System — CPE 8",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ─── AUTH HELPERS ────────────────────────────────────────────────
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        decoded = auth.verify_id_token(token)
        uid = decoded["uid"]
        user_ref = db.reference(f"users/{uid}").get()
        if not user_ref:
            raise HTTPException(status_code=404, detail="User not found")
        return {"uid": uid, "role": user_ref.get("role", ""), **user_ref}
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

def require_roles(allowed_roles: list):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access denied. Required: {allowed_roles}")
        return current_user
    return role_checker

ADMIN_ROLES = ["supervisor", "hr_admin", "manager", "super_admin"]

# ─── MODELS ──────────────────────────────────────────────────────
class TimeInRequest(BaseModel):
    time_in: str
    status: str

class TimeOutRequest(BaseModel):
    time_out: str
    total_hours: float
    extra_hours: Optional[float] = 0

class LeaveRequest(BaseModel):
    type: str
    start_date: str
    end_date: str
    reason: str

class StatusUpdate(BaseModel):
    status: str

class OTRequest(BaseModel):
    date: str
    hours: float
    reason: str

class ReportRequest(BaseModel):
    week_start: str
    week_end: str
    summary: str

class PayrollRequest(BaseModel):
    employee_uid: str
    period_start: str
    period_end: str
    cutoff: str
    basic_pay: float
    ot_pay: float
    incentives: float
    ot_hours: Optional[float] = 0
    ot_type: Optional[str] = "Regular Workday (×1.25)"
    hourly_rate: Optional[float] = 231

class UserCreate(BaseModel):
    uid: str
    display_name: str
    email: str
    role: str
    employee_id: str
    phone: Optional[str] = ""
    address: Optional[str] = ""

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    employee_id: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None

class BulkTimeOut(BaseModel):
    date: str
    employee_uids: list[str]

# ─── ROOT ────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "Summit PT Clinic API is running ✅", "version": "1.0.0", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "healthy"}

# ─── AUTH ────────────────────────────────────────────────────────
@app.post("/auth/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    return {
        "uid": current_user["uid"],
        "role": current_user["role"],
        "display_name": current_user.get("displayName"),
        "employee_id": current_user.get("employeeID"),
    }

# ─── ATTENDANCE ──────────────────────────────────────────────────
@app.post("/attendance/time-in", status_code=201)
async def time_in(data: TimeInRequest, current_user: dict = Depends(get_current_user)):
    uid = current_user["uid"]
    today = datetime.now().strftime("%Y-%m-%d")
    existing = db.reference(f"attendance/{uid}/{today}").get()
    if existing and existing.get("timeIn"):
        raise HTTPException(status_code=400, detail="Already timed in today")
    db.reference(f"attendance/{uid}/{today}").set({
        "timeIn": data.time_in, "timeOut": "", "totalHours": 0,
        "status": data.status, "extraHours": 0, "adminTimedOut": False
    })
    return {"message": "Time in recorded", "date": today, "time_in": data.time_in}

@app.post("/attendance/time-out")
async def time_out(data: TimeOutRequest, current_user: dict = Depends(get_current_user)):
    uid = current_user["uid"]
    today = datetime.now().strftime("%Y-%m-%d")
    existing = db.reference(f"attendance/{uid}/{today}").get()
    if not existing or not existing.get("timeIn"):
        raise HTTPException(status_code=400, detail="No time-in record found for today")
    if existing.get("timeOut"):
        raise HTTPException(status_code=400, detail="Already timed out today")
    db.reference(f"attendance/{uid}/{today}").update({
        "timeOut": data.time_out, "totalHours": data.total_hours, "extraHours": data.extra_hours or 0
    })
    return {"message": "Time out recorded", "total_hours": data.total_hours}

@app.get("/attendance/me")
async def get_my_attendance(current_user: dict = Depends(get_current_user)):
    records = db.reference(f"attendance/{current_user['uid']}").get()
    if not records:
        return {"records": []}
    return {"records": [{"date": d, **v} for d, v in records.items()]}

@app.get("/attendance/all")
async def get_all_attendance(date: Optional[str] = None, current_user: dict = Depends(require_roles(ADMIN_ROLES))):
    all_att   = db.reference("attendance").get() or {}
    all_users = db.reference("users").get() or {}
    result = []
    for uid, dates in all_att.items():
        user_info = all_users.get(uid, {})
        if user_info.get("role") in ADMIN_ROLES or user_info.get("status") == "inactive":
            continue
        if date:
            result.append({"uid": uid, "date": date, "display_name": user_info.get("displayName"), "employee_id": user_info.get("employeeID"), **dates.get(date, {})})
        else:
            for d, record in dates.items():
                result.append({"uid": uid, "date": d, "display_name": user_info.get("displayName"), "employee_id": user_info.get("employeeID"), **record})
    return {"records": result}

@app.post("/attendance/bulk-timeout")
async def bulk_timeout(data: BulkTimeOut, current_user: dict = Depends(require_roles(["supervisor", "hr_admin", "super_admin"]))):
    updated = []
    for uid in data.employee_uids:
        record = db.reference(f"attendance/{uid}/{data.date}").get()
        if record and record.get("timeIn") and not record.get("timeOut"):
            db.reference(f"attendance/{uid}/{data.date}").update({
                "timeOut": "05:00 PM", "totalHours": 8, "adminTimedOut": True,
                "adminTimedOutAt": datetime.now().strftime("%I:%M %p"),
                "adminTimedOutBy": current_user["uid"]
            })
            updated.append(uid)
    return {"message": f"Bulk time out applied to {len(updated)} employees", "updated": updated}

# ─── LEAVE ───────────────────────────────────────────────────────
@app.post("/leave", status_code=201)
async def file_leave(data: LeaveRequest, current_user: dict = Depends(get_current_user)):
    ref = db.reference(f"leave/{current_user['uid']}").push({
        "type": data.type, "startDate": data.start_date, "endDate": data.end_date,
        "reason": data.reason, "status": "Pending", "createdAt": datetime.now().strftime("%Y-%m-%d")
    })
    return {"message": "Leave request submitted", "id": ref.key}

@app.get("/leave/me")
async def get_my_leave(current_user: dict = Depends(get_current_user)):
    records = db.reference(f"leave/{current_user['uid']}").get()
    if not records:
        return {"records": []}
    return {"records": [{"id": k, **v} for k, v in records.items()]}

@app.get("/leave/all")
async def get_all_leave(current_user: dict = Depends(require_roles(["supervisor", "super_admin"]))):
    all_leave = db.reference("leave").get() or {}
    all_users = db.reference("users").get() or {}
    result = []
    for uid, leaves in all_leave.items():
        user_info = all_users.get(uid, {})
        for lid, data in leaves.items():
            result.append({"id": lid, "uid": uid, "display_name": user_info.get("displayName"), "employee_id": user_info.get("employeeID"), **data})
    return {"records": sorted(result, key=lambda x: x.get("createdAt", ""), reverse=True)}

@app.put("/leave/{uid}/{leave_id}/status")
async def update_leave_status(uid: str, leave_id: str, data: StatusUpdate, current_user: dict = Depends(require_roles(["supervisor", "super_admin"]))):
    if data.status not in ["Approved", "Rejected"]:
        raise HTTPException(status_code=400, detail="Status must be Approved or Rejected")
    leave = db.reference(f"leave/{uid}/{leave_id}").get()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    db.reference(f"leave/{uid}/{leave_id}").update({
        "status": data.status, "reviewedBy": current_user["uid"], "reviewedAt": datetime.now().strftime("%Y-%m-%d")
    })
    if data.status == "Approved":
        from datetime import date as date_type
        days = (datetime.strptime(leave["endDate"], "%Y-%m-%d").date() - datetime.strptime(leave["startDate"], "%Y-%m-%d").date()).days + 1
        user_data = db.reference(f"users/{uid}").get() or {}
        db.reference(f"users/{uid}").update({"leaveBalance": max(0, user_data.get("leaveBalance", 15) - days)})
    return {"message": f"Leave {data.status.lower()} successfully"}

# ─── OVERTIME ────────────────────────────────────────────────────
@app.post("/overtime", status_code=201)
async def file_overtime(data: OTRequest, current_user: dict = Depends(get_current_user)):
    ref = db.reference(f"overtime/{current_user['uid']}").push({
        "date": data.date, "hours": data.hours, "reason": data.reason,
        "status": "Pending", "createdAt": datetime.now().strftime("%Y-%m-%d")
    })
    return {"message": "OT request submitted", "id": ref.key}

@app.get("/overtime/me")
async def get_my_overtime(current_user: dict = Depends(get_current_user)):
    records = db.reference(f"overtime/{current_user['uid']}").get()
    if not records:
        return {"records": []}
    return {"records": [{"id": k, **v} for k, v in records.items()]}

@app.get("/overtime/all")
async def get_all_overtime(current_user: dict = Depends(require_roles(["supervisor", "super_admin"]))):
    all_ot    = db.reference("overtime").get() or {}
    all_users = db.reference("users").get() or {}
    result = []
    for uid, ots in all_ot.items():
        user_info = all_users.get(uid, {})
        for oid, data in ots.items():
            result.append({"id": oid, "uid": uid, "display_name": user_info.get("displayName"), "employee_id": user_info.get("employeeID"), **data})
    return {"records": sorted(result, key=lambda x: x.get("createdAt", ""), reverse=True)}

@app.put("/overtime/{uid}/{ot_id}/status")
async def update_ot_status(uid: str, ot_id: str, data: StatusUpdate, current_user: dict = Depends(require_roles(["supervisor", "super_admin"]))):
    if data.status not in ["Approved", "Rejected"]:
        raise HTTPException(status_code=400, detail="Status must be Approved or Rejected")
    if not db.reference(f"overtime/{uid}/{ot_id}").get():
        raise HTTPException(status_code=404, detail="OT request not found")
    db.reference(f"overtime/{uid}/{ot_id}").update({
        "status": data.status, "reviewedBy": current_user["uid"], "reviewedAt": datetime.now().strftime("%Y-%m-%d")
    })
    return {"message": f"OT {data.status.lower()} successfully"}

# ─── REPORTS ─────────────────────────────────────────────────────
@app.post("/reports", status_code=201)
async def submit_report(data: ReportRequest, current_user: dict = Depends(get_current_user)):
    ref = db.reference(f"reports/{current_user['uid']}").push({
        "weekStart": data.week_start, "weekEnd": data.week_end, "summary": data.summary,
        "status": "Pending", "createdAt": datetime.now().strftime("%Y-%m-%d")
    })
    return {"message": "Report submitted", "id": ref.key}

@app.get("/reports/me")
async def get_my_reports(current_user: dict = Depends(get_current_user)):
    records = db.reference(f"reports/{current_user['uid']}").get()
    if not records:
        return {"records": []}
    return {"records": [{"id": k, **v} for k, v in records.items()]}

@app.get("/reports/all")
async def get_all_reports(current_user: dict = Depends(require_roles(["manager", "super_admin"]))):
    all_reports = db.reference("reports").get() or {}
    all_users   = db.reference("users").get() or {}
    result = []
    for uid, reports in all_reports.items():
        user_info = all_users.get(uid, {})
        for rid, data in reports.items():
            result.append({"id": rid, "uid": uid, "display_name": user_info.get("displayName"), "employee_id": user_info.get("employeeID"), **data})
    return {"records": sorted(result, key=lambda x: x.get("createdAt", ""), reverse=True)}

@app.put("/reports/{uid}/{report_id}/status")
async def update_report_status(uid: str, report_id: str, data: StatusUpdate, current_user: dict = Depends(require_roles(["manager", "super_admin"]))):
    if data.status not in ["Approved", "Rejected"]:
        raise HTTPException(status_code=400, detail="Status must be Approved or Rejected")
    if not db.reference(f"reports/{uid}/{report_id}").get():
        raise HTTPException(status_code=404, detail="Report not found")
    db.reference(f"reports/{uid}/{report_id}").update({
        "status": data.status, "reviewedBy": current_user["uid"], "reviewedAt": datetime.now().strftime("%Y-%m-%d")
    })
    return {"message": f"Report {data.status.lower()} successfully"}

# ─── PAYROLL ─────────────────────────────────────────────────────
@app.post("/payroll", status_code=201)
async def generate_payroll(data: PayrollRequest, current_user: dict = Depends(require_roles(["hr_admin", "super_admin"]))):
    gross_pay = data.basic_pay + data.ot_pay + data.incentives
    ref = db.reference(f"payroll/{data.employee_uid}").push({
        "periodStart": data.period_start, "periodEnd": data.period_end, "cutoff": data.cutoff,
        "basicPay": data.basic_pay, "otPay": data.ot_pay, "incentives": data.incentives,
        "grossPay": gross_pay, "otHours": data.ot_hours, "otType": data.ot_type,
        "hourlyRate": data.hourly_rate, "generatedAt": datetime.now().strftime("%Y-%m-%d"),
        "generatedBy": current_user["uid"]
    })
    return {"message": "Payroll generated", "id": ref.key, "gross_pay": gross_pay}

@app.get("/payroll/me")
async def get_my_payroll(current_user: dict = Depends(get_current_user)):
    records = db.reference(f"payroll/{current_user['uid']}").get()
    if not records:
        return {"records": []}
    return {"records": sorted([{"id": k, **v} for k, v in records.items()], key=lambda x: x.get("generatedAt", ""), reverse=True)}

@app.get("/payroll/{uid}")
async def get_employee_payroll(uid: str, current_user: dict = Depends(require_roles(["hr_admin", "super_admin"]))):
    records = db.reference(f"payroll/{uid}").get()
    if not records:
        return {"records": []}
    return {"records": sorted([{"id": k, **v} for k, v in records.items()], key=lambda x: x.get("generatedAt", ""), reverse=True)}

# ─── USERS ───────────────────────────────────────────────────────
@app.get("/users")
async def get_all_users(current_user: dict = Depends(require_roles(ADMIN_ROLES))):
    users = db.reference("users").get() or {}
    return {"users": [{"uid": uid, **data} for uid, data in users.items()]}

@app.get("/users/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    user = db.reference(f"users/{current_user['uid']}").get()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"uid": current_user["uid"], **user}

@app.post("/users", status_code=201)
async def create_user(data: UserCreate, current_user: dict = Depends(require_roles(["hr_admin", "super_admin"]))):
    db.reference(f"users/{data.uid}").set({
        "displayName": data.display_name, "email": data.email, "role": data.role,
        "employeeID": data.employee_id, "phone": data.phone, "address": data.address,
        "status": "active", "leaveBalance": 15
    })
    return {"message": "User created", "uid": data.uid}

@app.put("/users/{uid}")
async def update_user(uid: str, data: UserUpdate, current_user: dict = Depends(require_roles(["hr_admin", "super_admin"]))):
    if not db.reference(f"users/{uid}").get():
        raise HTTPException(status_code=404, detail="User not found")
    updates = {k: v for k, v in {
        "displayName": data.display_name, "role": data.role, "employeeID": data.employee_id,
        "phone": data.phone, "address": data.address, "status": data.status
    }.items() if v is not None}
    db.reference(f"users/{uid}").update(updates)
    return {"message": "User updated"}

@app.put("/users/{uid}/status")
async def toggle_user_status(uid: str, data: StatusUpdate, current_user: dict = Depends(require_roles(["hr_admin", "super_admin"]))):
    if data.status not in ["active", "inactive"]:
        raise HTTPException(status_code=400, detail="Status must be active or inactive")
    db.reference(f"users/{uid}").update({"status": data.status})
    return {"message": f"User {data.status}"}
