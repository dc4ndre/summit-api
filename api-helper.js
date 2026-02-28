// ============================================================
// api.js — Place this in both React apps: src/api.js
// Replace direct Firebase calls with these API functions
// ============================================================

import { auth } from './firebase'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Get Firebase ID token for every request
const getToken = async () => {
  const user = auth.currentUser
  if (!user) throw new Error('Not authenticated')
  return await user.getIdToken()
}

// Base fetch wrapper
const apiCall = async (method, endpoint, body = null) => {
  const token = await getToken()
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    }
  }
  if (body) options.body = JSON.stringify(body)

  const res = await fetch(`${API_URL}${endpoint}`, options)
  const data = await res.json()

  if (!res.ok) throw new Error(data.detail || 'API error')
  return data
}

// ─── AUTH ────────────────────────────────────────────────────
export const verifyToken = () => apiCall('POST', '/auth/verify')

// ─── ATTENDANCE ──────────────────────────────────────────────
export const timeIn = (time_in, status) =>
  apiCall('POST', '/attendance/time-in', { time_in, status })

export const timeOut = (time_out, total_hours, extra_hours = 0) =>
  apiCall('POST', '/attendance/time-out', { time_out, total_hours, extra_hours })

export const getMyAttendance = () =>
  apiCall('GET', '/attendance/me')

export const getAllAttendance = (date = null) =>
  apiCall('GET', `/attendance/all${date ? `?date=${date}` : ''}`)

export const bulkTimeOut = (date, employee_uids) =>
  apiCall('POST', '/attendance/bulk-timeout', { date, employee_uids })

// ─── LEAVE ───────────────────────────────────────────────────
export const fileLeave = (type, start_date, end_date, reason) =>
  apiCall('POST', '/leave', { type, start_date, end_date, reason })

export const getMyLeave = () =>
  apiCall('GET', '/leave/me')

export const getAllLeave = () =>
  apiCall('GET', '/leave/all')

export const updateLeaveStatus = (uid, leaveId, status) =>
  apiCall('PUT', `/leave/${uid}/${leaveId}/status`, { status })

// ─── OVERTIME ────────────────────────────────────────────────
export const fileOvertime = (date, hours, reason) =>
  apiCall('POST', '/overtime', { date, hours, reason })

export const getMyOvertime = () =>
  apiCall('GET', '/overtime/me')

export const getAllOvertime = () =>
  apiCall('GET', '/overtime/all')

export const updateOTStatus = (uid, otId, status) =>
  apiCall('PUT', `/overtime/${uid}/${otId}/status`, { status })

// ─── REPORTS ─────────────────────────────────────────────────
export const submitReport = (week_start, week_end, summary) =>
  apiCall('POST', '/reports', { week_start, week_end, summary })

export const getMyReports = () =>
  apiCall('GET', '/reports/me')

export const getAllReports = () =>
  apiCall('GET', '/reports/all')

export const updateReportStatus = (uid, reportId, status) =>
  apiCall('PUT', `/reports/${uid}/${reportId}/status`, { status })

// ─── PAYROLL ─────────────────────────────────────────────────
export const generatePayroll = (data) =>
  apiCall('POST', '/payroll', data)

export const getMyPayroll = () =>
  apiCall('GET', '/payroll/me')

export const getEmployeePayroll = (uid) =>
  apiCall('GET', `/payroll/${uid}`)

// ─── USERS ───────────────────────────────────────────────────
export const getAllUsers = () =>
  apiCall('GET', '/users')

export const getMyProfile = () =>
  apiCall('GET', '/users/me')

export const createUser = (data) =>
  apiCall('POST', '/users', data)

export const updateUser = (uid, data) =>
  apiCall('PUT', `/users/${uid}`, data)

export const toggleUserStatus = (uid, status) =>
  apiCall('PUT', `/users/${uid}/status`, { status })
