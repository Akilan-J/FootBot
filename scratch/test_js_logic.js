function cleanMatchStatus(statusStr) {
  if (!statusStr) return 'LIVE';
  let clean = statusStr.trim();
  const lower = clean.toLowerCase();
  
  if (lower.includes('half time') || lower.includes('half-time') || lower.includes('halftime')) {
    return 'HT';
  }
  if (lower.includes('full time') || lower.includes('full-time') || lower.includes('fulltime')) {
    return 'FT';
  }
  if (lower.includes('extra time') || lower.includes('extra-time') || lower.includes('extratime')) {
    return 'ET';
  }
  if (lower.includes('postponed')) {
    return 'PP';
  }
  if (lower.includes('cancelled')) {
    return 'Can';
  }
  if (lower.includes('suspended')) {
    return 'Susp';
  }
  
  const minMatch = clean.match(/\b\d{1,2}\b/);
  if (minMatch) {
    const mins = minMatch[0];
    if (lower.includes('e+') || lower.includes('90+') || lower.includes('45+')) {
      const addedMatch = clean.match(/\d{1,2}\+\d/);
      if (addedMatch) return addedMatch[0] + "'";
    }
    return mins + "'";
  }
  
  clean = clean.replace(/,?\s*in progress/gi, '');
  clean = clean.replace(/minutes/gi, "'");
  clean = clean.trim();
  
  return clean || 'LIVE';
}

console.log("Test 1 (HT):", cleanMatchStatus("Half time , in progressHT"));
console.log("Test 2 (51 mins):", cleanMatchStatus("51 minutes , in progress51'"));
console.log("Test 3 (90+3 mins):", cleanMatchStatus("90+3 , in progress90+3'"));
console.log("Test 4 (FT):", cleanMatchStatus("Full timeFT"));
console.log("Test 5 (Empty):", cleanMatchStatus(""));
