"""Short, bounded jumps between nearby visible perches."""
import math

GRAVITY = 600.0


def jump_velocity(dx, dy, max_rise=110, max_duration=1.6):
    rise = max(30, -dy + 25)
    if (max_rise is not None and rise > max_rise) or abs(dx) > 180:
        return None
    vy = -math.sqrt(2 * GRAVITY * rise)
    discriminant = vy * vy + 2 * GRAVITY * dy
    if discriminant < 0:
        return None
    duration = (-vy + math.sqrt(discriminant)) / GRAVITY
    if duration < 0.25 or (max_duration is not None and duration > max_duration):
        return None
    vx = dx / duration
    return (vx, vy) if abs(vx) <= 130 else None
