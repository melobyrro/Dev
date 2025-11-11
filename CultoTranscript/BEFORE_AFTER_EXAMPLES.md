# Before & After: Sermon Date Prefix Implementation

## Overview

This document shows concrete examples of how video titles change with the new date prefix implementation.

---

## Example 1: New Video Ingestion

### Before Implementation

**YouTube Title**: `Culto de Domingo`
**Published**: March 17, 2024 (Sunday)

**Database**:
```
title: "Culto de Domingo"
sermon_actual_date: 2024-03-17
```

**Frontend Display** (JavaScript adds date):
```
03/17/2024 - Culto de Domingo
```

**Problem**: Date only appears in UI, not stored in database

---

### After Implementation

**YouTube Title**: `Culto de Domingo`
**Published**: March 17, 2024 (Sunday)

**Database**:
```
title: "03/17/2024 - Culto de Domingo"
sermon_actual_date: 2024-03-17
```

**Frontend Display** (date from database):
```
03/17/2024 - Culto de Domingo
```

**Benefit**: Date is permanent, searchable, and consistent across all views

---

## Example 2: Video with Existing Date Prefix

### Before Implementation

**YouTube Title**: `15/03/2024 - Pregação Especial`
**Published**: March 18, 2024 (Monday)

**Database**:
```
title: "15/03/2024 - Pregação Especial"
sermon_actual_date: 2024-03-17  (previous Sunday)
```

**Frontend Display** (adds another date):
```
03/17/2024 - 15/03/2024 - Pregação Especial  ❌ DUPLICATE!
```

**Problem**: Duplicate dates confuse users

---

### After Implementation

**YouTube Title**: `15/03/2024 - Pregação Especial`
**Published**: March 18, 2024 (Monday)

**Database** (old prefix removed, sermon date added):
```
title: "03/17/2024 - Pregação Especial"
sermon_actual_date: 2024-03-17  (previous Sunday)
```

**Frontend Display**:
```
03/17/2024 - Pregação Especial  ✓ CLEAN!
```

**Benefit**: No duplicates, uses correct sermon date

---

## Example 3: Migration of Existing Videos

### Before Migration

**Database**:
```sql
id |       title        | sermon_actual_date
---+--------------------+-------------------
 1 | Culto de Domingo   | 2024-01-07
 2 | Louvor e Adoração  | 2024-01-14
 3 | Pregação Especial  | 2024-01-21
```

**Frontend Display** (JavaScript formatting):
```
01/07/2024 - Culto de Domingo
01/14/2024 - Louvor e Adoração
01/21/2024 - Pregação Especial
```

---

### After Migration

**Run Migration Script**:
```bash
docker-compose exec culto_web python scripts/update_video_titles_with_dates.py
```

**Output**:
```
2025-11-10 12:00:00 - INFO - Starting video title migration...
2025-11-10 12:00:00 - INFO - Found 3 videos to process
2025-11-10 12:00:01 - INFO - [1/3] Updating video 1
2025-11-10 12:00:01 - INFO -   Old: Culto de Domingo
2025-11-10 12:00:01 - INFO -   New: 01/07/2024 - Culto de Domingo
2025-11-10 12:00:01 - INFO - [2/3] Updating video 2
2025-11-10 12:00:01 - INFO -   Old: Louvor e Adoração
2025-11-10 12:00:01 - INFO -   New: 01/14/2024 - Louvor e Adoração
2025-11-10 12:00:01 - INFO - [3/3] Updating video 3
2025-11-10 12:00:01 - INFO -   Old: Pregação Especial
2025-11-10 12:00:01 - INFO -   New: 01/21/2024 - Pregação Especial
2025-11-10 12:00:01 - INFO - Migration complete!
2025-11-10 12:00:01 - INFO -   Total videos: 3
2025-11-10 12:00:01 - INFO -   Updated: 3
2025-11-10 12:00:01 - INFO -   Skipped: 0
```

**Database**:
```sql
id |              title               | sermon_actual_date
---+----------------------------------+-------------------
 1 | 01/07/2024 - Culto de Domingo    | 2024-01-07
 2 | 01/14/2024 - Louvor e Adoração   | 2024-01-14
 3 | 01/21/2024 - Pregação Especial   | 2024-01-21
```

**Frontend Display** (directly from database):
```
01/07/2024 - Culto de Domingo
01/14/2024 - Louvor e Adoração
01/21/2024 - Pregação Especial
```

---

## Example 4: Monthly Grouping

### Before Implementation

**Videos in March 2024**:
```javascript
// JavaScript groups by sermon_actual_date
// Displays with date prefix added in UI
Março de 2024:
  03/03/2024 - Culto Matinal
  03/10/2024 - Pregação da Semana
  03/17/2024 - Louvor e Adoração
  03/24/2024 - Culto de Domingo
  03/31/2024 - Culto Especial
```

---

### After Implementation

**Videos in March 2024**:
```javascript
// JavaScript groups by sermon_actual_date
// Displays title directly from database
Março de 2024:
  03/03/2024 - Culto Matinal
  03/10/2024 - Pregação da Semana
  03/17/2024 - Louvor e Adoração
  03/24/2024 - Culto de Domingo
  03/31/2024 - Culto Especial
```

**Result**: Same display, but now dates are searchable in database queries

---

## Example 5: Video Detail Page

### Before Implementation

**URL**: `/video/123`

**Display**:
```html
<h1>Culto de Domingo</h1>  <!-- No date in title -->
<p>Data do Culto: 17/03/2024</p>  <!-- Separate field -->
```

---

### After Implementation

**URL**: `/video/123`

**Display**:
```html
<h1>03/17/2024 - Culto de Domingo</h1>  <!-- Date in title -->
<p>Data do Culto: 17/03/2024</p>  <!-- Still available separately -->
```

**Benefit**: Date is visible in browser tab, bookmarks, and search results

---

## Example 6: Database Search

### Before Implementation

**Search for videos in March 2024**:
```sql
SELECT title FROM videos
WHERE sermon_actual_date >= '2024-03-01'
  AND sermon_actual_date < '2024-04-01';

-- Results (no dates in titles):
Culto de Domingo
Pregação Especial
Louvor e Adoração
```

**Search by title text**:
```sql
SELECT title FROM videos WHERE title LIKE '%03/17/2024%';

-- Results: NONE (date not in database)
```

---

### After Implementation

**Search for videos in March 2024**:
```sql
SELECT title FROM videos
WHERE sermon_actual_date >= '2024-03-01'
  AND sermon_actual_date < '2024-04-01';

-- Results (with dates in titles):
03/03/2024 - Culto de Domingo
03/17/2024 - Pregação Especial
03/24/2024 - Louvor e Adoração
```

**Search by title text**:
```sql
SELECT title FROM videos WHERE title LIKE '%03/17/2024%';

-- Results:
03/17/2024 - Pregação Especial
```

**Benefit**: Can search by date string in title

---

## Example 7: API Response

### Before Implementation

**GET /api/videos/123**
```json
{
  "id": 123,
  "title": "Culto de Domingo",
  "sermon_actual_date": "2024-03-17",
  "published_at": "2024-03-17T10:00:00Z"
}
```

**Client must format**: Client-side JavaScript adds date prefix

---

### After Implementation

**GET /api/videos/123**
```json
{
  "id": 123,
  "title": "03/17/2024 - Culto de Domingo",
  "sermon_actual_date": "2024-03-17",
  "published_at": "2024-03-17T10:00:00Z"
}
```

**Client displays directly**: No client-side formatting needed

**Benefit**: Consistent across all API consumers (web, mobile, integrations)

---

## Example 8: Edge Cases

### Case 1: Video Without sermon_actual_date

**Database**:
```
title: "Old Imported Video"
sermon_actual_date: NULL
```

**After Implementation**:
```
title: "Old Imported Video"  (unchanged)
sermon_actual_date: NULL
```

**Migration Output**:
```
2025-11-10 12:00:00 - WARNING - Video 999 has no sermon_actual_date, skipping
```

---

### Case 2: Video Published on Wednesday

**YouTube Title**: `Estudo Bíblico Noturno`
**Published**: March 20, 2024 (Wednesday)

**sermon_actual_date Calculation**:
- Published: Wednesday (March 20)
- Previous Sunday: March 17, 2024

**Database**:
```
title: "03/17/2024 - Estudo Bíblico Noturno"
sermon_actual_date: 2024-03-17
```

**Note**: Uses "previous Sunday" logic, not publish date

---

### Case 3: Portuguese Date Format in YouTube Title

**YouTube Title**: `15 de março de 2024 - Culto Especial`
**Published**: March 17, 2024

**Processing**:
1. Remove Portuguese date prefix: `Culto Especial`
2. Add US format date: `03/17/2024 - Culto Especial`

**Database**:
```
title: "03/17/2024 - Culto Especial"
sermon_actual_date: 2024-03-17
```

---

## Summary of Benefits

### User Experience
✅ Consistent date display across all pages
✅ No duplicate dates in titles
✅ Dates visible in browser tabs and bookmarks
✅ Cleaner, more professional appearance

### Developer Experience
✅ Simplified frontend code (no client-side formatting)
✅ Database queries can search by title text
✅ API responses are ready to display
✅ Single source of truth for display format

### Data Integrity
✅ Dates stored permanently in database
✅ Survives database exports/imports
✅ Searchable and sortable by title
✅ Consistent across all views and exports

---

**Implementation Date**: 2025-11-10
**Format**: MM/DD/YYYY - [Original Title]
