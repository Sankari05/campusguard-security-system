/**
 * frontend/js/utils/validators.js
 * ===============================
 * Field validators for Student Enrollment, Faculty, and HOD forms.
 * Aligns 100% with backend Pydantic schema validation rules.
 */

export const NAME_REGEX = /^[A-Za-z]+( [A-Za-z]+)*$/;
export const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const ROLL_NUMBER_REGEX = /^[A-Za-z0-9_-]{3,20}$/;

/**
 * Validates a name string (First Name, Last Name)
 * @param {string} value
 * @param {string} label - e.g., 'First Name'
 * @returns {string} Error message or empty string if valid
 */
export function validateName(value, label = 'Name') {
  const v = (value || '').trim();
  if (!v) return `${label} is required.`;
  if (v.length < 3) return `${label} must be at least 3 characters.`;
  if (v.length > 50) return `${label} must not exceed 50 characters.`;
  if (/[0-9]/.test(v)) return `${label} must not contain numbers.`;
  if (/[^A-Za-z ]/.test(v)) return `${label} must not contain special characters.`;
  if (!NAME_REGEX.test(v))
    return `${label} must contain only letters and single spaces between words.`;
  return '';
}

/**
 * Validates institutional Roll / Register Number
 */
export function validateRollNumber(roll) {
  const r = (roll || '').trim();
  if (!r) return 'Roll / Register number is required.';
  if (r.length < 3 || r.length > 20) return 'Roll number must be between 3 and 20 characters.';
  if (!ROLL_NUMBER_REGEX.test(r))
    return 'Roll number can only contain alphanumeric characters, underscores, and hyphens.';
  return '';
}

/**
 * Validates email format
 */
export function validateEmail(email) {
  const e = (email || '').trim();
  if (!e) return 'Email address is required.';
  if (!EMAIL_REGEX.test(e)) return 'Please enter a valid email address.';
  return '';
}

/**
 * Calculates completed age from YYYY-MM-DD
 */
export function calculateAge(dobStr) {
  if (!dobStr) return -1;
  const dob = new Date(dobStr);
  if (isNaN(dob.getTime())) return -1;
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const m = today.getMonth() - dob.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) {
    age--;
  }
  return age;
}

/**
 * Validates Date of Birth based on institutional role
 */
export function validateDateOfBirth(dobStr, role = 'student') {
  if (!dobStr) return 'Date of Birth is required.';
  const dob = new Date(dobStr);
  if (isNaN(dob.getTime())) return 'Invalid calendar date.';
  if (dob > new Date()) return 'Date of Birth cannot be in the future.';

  const age = calculateAge(dobStr);
  const r = (role || 'student').toLowerCase();

  if (r === 'student') {
    if (age < 17 || age > 50) return 'Student age must be between 17 and 50 years.';
  } else if (r === 'faculty' || r === 'teacher') {
    if (age < 21) return 'Faculty age must be at least 21 years.';
  } else if (r === 'hod') {
    if (age < 30) return 'HOD age must be at least 30 years.';
  }
  return '';
}

export default {
  validateName,
  validateRollNumber,
  validateEmail,
  calculateAge,
  validateDateOfBirth,
};
