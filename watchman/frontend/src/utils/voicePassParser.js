/**
 * Voice Input NLP Parser for CampusGuard Digital Self-Pass
 * Supports English, Tamil (தமிழ்), and Tanglish (Tamil + English)
 */

const TAMIL_NUMBER_WORDS = {
  'பூஜ்ஜியம்': '0', 'ஜீரோ': '0', 'zero': '0',
  'ஒன்று': '1', 'ஒன்னு': '1', 'one': '1',
  'இரண்டு': '2', 'ரெண்டு': '2', 'two': '2',
  'மூன்று': '3', 'மூணு': '3', 'three': '3',
  'நான்கு': '4', 'நாலு': '4', 'four': '4',
  'ஐந்து': '5', 'அஞ்சு': '5', 'five': '5',
  'ஆறு': '6', 'six': '6',
  'ஏழு': '7', 'seven': '7',
  'எட்டு': '8', 'eight': '8',
  'ஒன்பது': '9', 'nine': '9'
};

/**
 * Normalizes spoken numbers into standard digit strings
 */
export const normalizeSpokenDigits = (text) => {
  if (!text) return '';
  let str = text.toLowerCase();
  
  // Replace number words with digits
  for (const [word, digit] of Object.entries(TAMIL_NUMBER_WORDS)) {
    const reg = new RegExp(`\\b${word}\\b`, 'gi');
    str = str.replace(reg, digit);
  }
  
  // Collapse spaced digits: e.g. "9 8 4 0 1 2 3 4 5 6" -> "9840123456"
  str = str.replace(/(\d)\s+(\d)/g, '$1$2');
  str = str.replace(/(\d)\s+(\d)/g, '$1$2');
  str = str.replace(/(\d)\s+(\d)/g, '$1$2');
  
  return str;
};

/**
 * Extracts a 10-digit Indian mobile number from text
 */
export const extractPhoneNumber = (text) => {
  if (!text) return '';
  const normalized = normalizeSpokenDigits(text);
  
  // Look for standard 10 digit number starting with 6, 7, 8, or 9
  const match = normalized.match(/\b([6-9]\d{9})\b/);
  if (match) return match[1];

  // Fallback: look for 10 consecutive digits anywhere
  const digitsOnly = normalized.replace(/\D/g, '');
  if (digitsOnly.length === 10 && /^[6-9]/.test(digitsOnly)) {
    return digitsOnly;
  }
  if (digitsOnly.length > 10) {
    const sub = digitsOnly.match(/([6-9]\d{9})/);
    if (sub) return sub[1];
  }
  return '';
};

/**
 * Extracts student roll number or staff ID
 */
export const extractIdentifier = (text) => {
  if (!text) return '';
  const clean = text.toUpperCase();
  
  // Standard college roll no formats: e.g. 22CS101, 21IT045, 23ME012, 22AIDS05
  const rollMatch = clean.match(/\b(\d{2}[A-Z]{2,4}\d{2,4})\b/);
  if (rollMatch) return rollMatch[1];

  // Staff ID format: e.g. STF-8821 or STF8821
  const staffMatch = clean.match(/\b(STF-?\d{3,6})\b/);
  if (staffMatch) return staffMatch[1];

  // Explicit keyword detection: "roll no 101", "id 8821"
  const kwMatch = text.match(/(?:roll\s*(?:no|number)?|staff\s*id|id)\s*(?:is|:)?\s*([a-zA-Z0-9_-]+)/i);
  if (kwMatch && kwMatch[1]) {
    return kwMatch[1].toUpperCase();
  }

  return '';
};

/**
 * Detects visitor type: STUDENT, STAFF, PARENT, or OTHERS
 */
export const detectVisitorType = (text) => {
  if (!text) return null;
  const lower = text.toLowerCase();

  // Parent indicators
  if (
    lower.includes('parent') ||
    lower.includes('பெற்றோர்') ||
    lower.includes('appa') ||
    lower.includes('amma') ||
    lower.includes('father') ||
    lower.includes('mother') ||
    lower.includes('paiyan') ||
    lower.includes('ponnu') ||
    lower.includes('daughter') ||
    lower.includes('son')
  ) {
    return 'PARENT';
  }

  // Staff indicators
  if (
    lower.includes('staff') ||
    lower.includes('professor') ||
    lower.includes('faculty') ||
    lower.includes('பணியாளர்') ||
    lower.includes('ஆசிரியர்') ||
    lower.includes('lecturer') ||
    lower.includes('valuation')
  ) {
    return 'STAFF';
  }

  // Others / Vendor / Visitor indicators
  if (
    lower.includes('vendor') ||
    lower.includes('delivery') ||
    lower.includes('courier') ||
    lower.includes('interview') ||
    lower.includes('விருந்தினர்') ||
    lower.includes('recruiter') ||
    lower.includes('repair') ||
    lower.includes('visitor')
  ) {
    return 'OTHERS';
  }

  // Student indicators
  if (
    lower.includes('student') ||
    lower.includes('மாணவர்') ||
    lower.includes('roll no') ||
    lower.includes('roll number') ||
    lower.includes('bus miss') ||
    lower.includes('missed bus') ||
    lower.includes('traffic delay') ||
    lower.includes('class') ||
    lower.includes('lab')
  ) {
    return 'STUDENT';
  }

  return null;
};

/**
 * Matches college department from speech
 */
export const matchDepartment = (text) => {
  if (!text) return null;
  const lower = text.toLowerCase();

  if (lower.includes('computer') || lower.includes('cse') || lower.includes('கணினி')) {
    return 'Computer Science (B.Tech)';
  }
  if (lower.includes('information') || lower.includes(' it ') || lower.endsWith(' it') || lower.includes('தகவல்')) {
    return 'Information Technology (B.Tech)';
  }
  if (lower.includes('mech') || lower.includes('mechanical') || lower.includes('இயந்திர')) {
    return 'Mechanical Engineering';
  }
  if (lower.includes('ece') || lower.includes('electronics & comm') || lower.includes('electronics and comm')) {
    return 'Electronics & Comm (ECE)';
  }
  if (lower.includes('eee') || lower.includes('electrical')) {
    return 'Electrical & Electronics (EEE)';
  }
  if (lower.includes('civil') || lower.includes('கட்டுமான')) {
    return 'Civil Engineering';
  }
  if (lower.includes('ai') || lower.includes('data science') || lower.includes('aids')) {
    return 'Artificial Intelligence & Data Science';
  }
  if (lower.includes('mba') || lower.includes('management')) {
    return 'Management Studies (MBA)';
  }
  if (lower.includes('principal') || lower.includes('admin') || lower.includes('முதல்வர்')) {
    return 'Administration / Principal Office';
  }

  return null;
};

/**
 * Matches common reason for late arrival or visit
 */
export const matchReason = (text, visitorType = 'STUDENT') => {
  if (!text) return null;
  const lower = text.toLowerCase();

  if (visitorType === 'STUDENT') {
    if (lower.includes('bus') || lower.includes('traffic') || lower.includes('missed') || lower.includes('பேருந்து')) {
      return 'Missed College Bus (Traffic Delay)';
    }
    if (lower.includes('hospital') || lower.includes('doctor') || lower.includes('medical') || lower.includes('clinic') || lower.includes('மருத்துவம்')) {
      return 'Medical Clinic / Hospital Visit';
    }
    if (lower.includes('project') || lower.includes('lab') || lower.includes('ஆய்வகம்')) {
      return 'Special Project / Lab Work';
    }
    if (lower.includes('train') || lower.includes('transit') || lower.includes('ரயில்')) {
      return 'Train / Public Transit Delay';
    }
    if (lower.includes('family') || lower.includes('emergency') || lower.includes('personal') || lower.includes('அவசரம்')) {
      return 'Family Emergency / Personal Reason';
    }
  }

  if (visitorType === 'STAFF') {
    if (lower.includes('meeting') || lower.includes('கூட்டம்')) {
      return 'Official Department Meeting';
    }
    if (lower.includes('guest') || lower.includes('lecture')) {
      return 'Guest Lecture / Visiting Faculty';
    }
    if (lower.includes('exam') || lower.includes('valuation') || lower.includes('தேர்வு')) {
      return 'University Exam Valuation Duty';
    }
    if (lower.includes('lab') || lower.includes('research')) {
      return 'Research Lab Supervision';
    }
  }

  if (visitorType === 'PARENT') {
    if (lower.includes('principal') || lower.includes('hod') || lower.includes('academic') || lower.includes('முதல்வர்')) {
      return 'Meeting Principal / HOD Regarding Academic Progress';
    }
    if (lower.includes('fee') || lower.includes('fees') || lower.includes('payment') || lower.includes('scholarship') || lower.includes('கட்டணம்')) {
      return 'Tuition Fee & Scholarship Payment Desk';
    }
    if (lower.includes('hostel') || lower.includes('warden') || lower.includes('leave') || lower.includes('விடுதி')) {
      return 'Hostel Warden Meeting / Leave Formalities';
    }
    if (lower.includes('certificate') || lower.includes('verification') || lower.includes('சான்றிதழ்')) {
      return 'Original Certificates Submission / Verification';
    }
  }

  if (visitorType === 'OTHERS') {
    if (lower.includes('delivery') || lower.includes('equipment') || lower.includes('vendor') || lower.includes('பொருள்')) {
      return 'Vendor / Lab Equipment Delivery';
    }
    if (lower.includes('placement') || lower.includes('interview') || lower.includes('drive') || lower.includes('நேர்காணல்')) {
      return 'Placement Recruiter & Campus Drive';
    }
    if (lower.includes('maintenance') || lower.includes('repair') || lower.includes('பழுது')) {
      return 'Campus Facility Maintenance & Repairs';
    }
    if (lower.includes('admission') || lower.includes('enquiry') || lower.includes('சேர்க்கை')) {
      return 'Student Admission Enquiry';
    }
  }

  return null;
};

/**
 * Extracts visitor's name from speech
 */
export const extractName = (text) => {
  if (!text) return '';
  
  // Clean prefixes: "my name is", "en peru", "en peyar", "என் பெயர்", "naan", "name"
  const patterns = [
    /(?:my\s*name\s*is|name\s*is|en\s*peyar\s*(?:is|aana)?|en\s*peru\s*(?:is)?|என்\s*பெயர்\s*(?:ஆகிய)?|பெயர்\s*(?:ஆகிய)?|naan|நான்)\s+([a-zA-Z\u0B80-\u0BFF\s.]{2,30}?)(?=\s+(?:phone|mobile|number|roll|from|department|dept|reason|paaka|meet|vanthurukken|vandhen|vandhirukken|contact|studying|and|,|$))/i,
    /^(?:this\s*is|naan|நான்)\s+([a-zA-Z\u0B80-\u0BFF\s.]{2,30})/i
  ];

  for (const pat of patterns) {
    const match = text.match(pat);
    if (match && match[1]) {
      let name = match[1].trim();
      // Capitalize first letters of words
      name = name.replace(/\b\w/g, (c) => c.toUpperCase());
      return name;
    }
  }

  return '';
};

/**
 * Extracts person to meet (for Others / Parents)
 */
export const extractPersonToMeet = (text) => {
  if (!text) return '';
  const match = text.match(/(?:meet|paaka|பார்க்க|whom\s*to\s*meet|meeting)\s+([a-zA-Z\u0B80-\u0BFF\s.]{2,30}?)(?=\s+(?:for|regarding|in|dept|department|office|and|,|$))/i);
  if (match && match[1]) {
    let p = match[1].trim();
    return p.replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return '';
};

/**
 * Master parser: takes raw speech transcript and returns structured fields
 */
export const parseSpokenVisitorPass = (transcript, currentVisitorType = 'STUDENT') => {
  if (!transcript || typeof transcript !== 'string') return {};

  const detectedType = detectVisitorType(transcript) || currentVisitorType;
  const phoneNumber = extractPhoneNumber(transcript);
  const identifier = extractIdentifier(transcript);
  const name = extractName(transcript);
  const department = matchDepartment(transcript);
  const reason = matchReason(transcript, detectedType);
  const personToMeet = extractPersonToMeet(transcript);

  return {
    visitorType: detectedType,
    name,
    phoneNumber,
    identifier,
    department,
    reason,
    personToMeet,
    rawText: transcript
  };
};
