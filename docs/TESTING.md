# Miner Testing Sandbox Guide

The Miner Testing Sandbox allows you to test your fingerprinting script in an isolated environment without needing to set up a full challenge session.

## Accessing the Sandbox

Navigate to the miner test page:

```
http://localhost:8000/miner-test
```

## How to Use

### 1. Submit a Fingerprint

1. Enter a **Device Label** (e.g., `device-1`, `chrome-desktop`, `iphone-12`)
2. Click **Submit Fingerprint**
3. The system will:
   - Run `pre-process` to clean the environment
   - Execute `fingerprinter.js` to generate a fingerprint hash
   - Submit the fingerprint to the backend

### 2. View Results

Click **View Results** to see:
- **Score**: Your final score (0.000 to 1.000)
- **Breakdown**: Correct, Collisions, and Fragmentations count
- **Devices**: List of all collected fingerprints

### 3. Clean Session

Click **Clean Session** to reset all collected data and start fresh.

## Scoring Rules

The scoring system uses a **Two-Strike** rule to evaluate your fingerprinting script:

### 1. Fragmentation (Internal Consistency)

Measures how many unique fingerprints your script generates for the same device.

| Unique Hashes | Points |
|---------------|--------|
| 1 | +1.0 (Perfect) |
| 2 | +0.7 (Penalty: -0.3) |
| 3+ | 0.0 (Failed) |

- **Correct**: 1 unique hash per device = 1.0 points
- **Fragmentations**: More than 1 unique hash = penalty applied

### 2. Collision (External Uniqueness)

Measures if the same fingerprint hash appears across different physical devices.

| Collision Count | Points |
|-----------------|--------|
| 0 | No penalty |
| 1 | -0.25 penalty |
| 2+ | 0.0 (Failed) |

### 3. Final Score Calculation

```
Final Score = Total Device Points / Number of Devices
```

The score is normalized to a value between 0.0 and 1.0.

### Example Scoring

| Submission | Device | Hash | Score Impact |
|------------|--------|------|--------------|
| 1 | device-1 | hash-A | +1.0 (correct) |
| 2 | device-2 | hash-B | +1.0 (correct) |
| 3 | device-1 | hash-A | +1.0 (same hash, no penalty) |
| | | **Total** | **3.0 / 3 = 1.0** |

---

## API Endpoints

### GET /miner-test

Renders the miner testing sandbox page.

### POST /collect

Submits a fingerprint for the current session.

**Request Body:**
```json
{
  "device_label": "device-1",
  "fingerprint_hash": "abc123..."
}
```

### GET /results

Returns the current scoring results.

**Response:**
```json
{
  "devices": [...],
  "score": 0.85,
  "breakdown": {
    "correct": 5,
    "collisions": 1,
    "fragmentations": 2
  }
}
```

### POST /clean

Clears all collected fingerprints and resets the session.

---

## Testing Tips

1. **Use unique device labels**: Each physical device should have a distinct label (e.g., `iphone-12`, `pixel-6`, `desktop-pc`)

2. **Test multiple submissions**: Submit fingerprints multiple times from the same device to test consistency

3. **Test across devices**: Use different browsers or devices to test collision detection

4. **Check results frequently**: Use "View Results" to understand how your fingerprinting script is performing
