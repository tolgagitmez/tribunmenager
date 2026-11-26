"""Derive descriptive attack intensity from existing sampled native telemetry."""
import math


def pair(sample, key, *, integer=False):
    value = sample.get(key)
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Invalid ' + key)
    if any(type(n) not in ((int,) if integer else (int, float)) or not math.isfinite(n) or n < 0 for n in value):
        raise ValueError('Invalid ' + key)
    return value


def ratio(numerator, denominator, scale=100):
    return round(scale * numerator / denominator, 3) if denominator else None


def attack_intensity(sample):
    if sample is None:
        return None
    if not isinstance(sample, dict):
        raise ValueError('Invalid sampled telemetry')
    observed = sample.get('observedOpenPlayMs')
    if type(observed) is not int or observed < 0:
        raise ValueError('Invalid observedOpenPlayMs')
    control = pair(sample, 'controlledMs', integer=True)
    final = pair(sample, 'controlledFinalThirdMs', integer=True)
    box = pair(sample, 'controlledBoxMs', integer=True)
    carrier = pair(sample, 'sameCarrierMs', integer=True)
    forward = pair(sample, 'controlledForwardMeters')
    backward = pair(sample, 'controlledBackwardMeters')
    entries = pair(sample, 'controlledBoxCrossings', integer=True)
    crossings = pair(sample, 'observedBoxCrossings', integer=True)
    if sum(control) > observed or any(final[t] > control[t] or box[t] > final[t] or carrier[t] > control[t] or entries[t] > crossings[t] for t in range(2)):
        raise ValueError('Inconsistent sampled attack telemetry')
    if (observed == 0 and any(crossings)) or any(carrier[t] == 0 and (forward[t] or backward[t]) for t in range(2)):
        raise ValueError('Movement without observation time')
    return {
        'observedOpenPlayMs': observed,
        'controlledMs': control,
        'controlledFinalThirdMs': final,
        'controlledBoxMs': box,
        'sameCarrierMs': carrier,
        'controlledForwardMeters': forward,
        'controlledBackwardMeters': backward,
        'controlledBoxCrossings': entries,
        'finalThirdShareOfControlledPercent': [ratio(final[t], control[t]) for t in range(2)],
        'boxShareOfControlledPercent': [ratio(box[t], control[t]) for t in range(2)],
        'entriesPerObservedOpenPlayMinute': [ratio(entries[t], observed, 60000) for t in range(2)],
        'netForwardMetersPerSameCarrierMinute': [ratio(forward[t]-backward[t], carrier[t], 60000) for t in range(2)],
        'scope': 'Sampled elapsed-time intervals, both teams. Same-carrier net displacement is not dribble count. Entry rates use shared observed open-play minutes, not nominal 90 minutes. Missing or zero denominators are not success.'
    }
