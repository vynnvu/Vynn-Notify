"""Bounded Dijkstra routing and swept rectangular collision, no Qt/Win32."""
from dataclasses import dataclass
import heapq
import math
import time
from pet.behavior import GRAVITY, jump_velocity


@dataclass(frozen=True)
class Ledge:
    key: object
    left: float
    top: float
    right: float
    bottom: float
    solid: bool = True
    owner: object = None
    space: str = 'desktop'
    kind: str = 'object'


@dataclass(frozen=True)
class Step:
    kind: str
    key: object
    x: float
    y: float
    vx: float = 0
    vy: float = 0


def overlaps(x, y, w, h, rect):
    return x+w > rect.left+.5 and x < rect.right-.5 and y+h > rect.top+.5 and y < rect.bottom-.5


def clear_arc(x, feet, tx, ty, velocity, ledges, width, height, ceiling):
    vx, vy = velocity
    duration = (-vy + math.sqrt(vy*vy+2*GRAVITY*(ty-feet)))/GRAVITY
    samples = max(12, math.ceil(duration*90))
    for i in range(1, samples):
        t = duration*i/samples
        px, py = x+vx*t-width/2, feet+vy*t+GRAVITY*t*t/2-height
        if py < ceiling:
            return False
        for rect in ledges:
            if rect.solid and overlaps(px, py, width, height, rect):
                # Starting within a UI group is allowed to leave it.
                if not overlaps(x-width/2, feet-height, width, height, rect):
                    return False
    return True


def plan_route(start_x, start_feet, start_key, target_key, ledges, width, height,
               floor, left, right, ceiling, max_nodes=220):
    """Sample wide perches and ground; find a walk/jump/climb chain."""
    if not any(r.key == target_key for r in ledges):
        return []
    ground = Ledge(None, left, floor, right, floor+1, False)
    target = next(r for r in ledges if r.key == target_key)
    preferred = [r for r in ledges if r.key in (target_key, start_key)]
    rest = sorted((r for r in ledges if r.key not in (target_key, start_key)),
                  key=lambda r: min(abs((r.left+r.right)/2-start_x)+abs(r.top-start_feet),
                                    abs((r.left+r.right-target.left-target.right)/2)+abs(r.top-target.top)))
    surfaces = [ground] + (preferred+rest)[:60]
    nodes = [(start_key, start_x, start_feet)]
    by_key = {r.key: r for r in surfaces}
    for r in surfaces:
        if r.top < ceiling+height or r.right-r.left < 20:
            continue
        lo, hi = max(left+width/2, r.left+8), min(right-width/2, r.right-8)
        if lo > hi:
            continue
        xs = {lo, hi, max(lo, min(hi, start_x)), (lo+hi)/2}
        xs.update(lo+i*100 for i in range(1, min(12, math.ceil((hi-lo)/100))) if lo+i*100 < hi)
        for x in sorted(xs):
            nodes.append((r.key, x, r.top))
            if len(nodes) >= max_nodes:
                break
        if len(nodes) >= max_nodes:
            break
    queue, distance, parent = [(0, 0)], {0: 0}, {}
    deadline = time.monotonic()+1.5
    while queue:
        if time.monotonic() > deadline:
            return []
        cost, index = heapq.heappop(queue)
        if cost != distance.get(index):
            continue
        key, x, y = nodes[index]
        if key == target_key and index:
            route = []
            while index:
                previous, step = parent[index]
                route.append(step)
                index = previous
            return route[::-1]
        for j, (other, tx, ty) in enumerate(nodes):
            if j == index or abs(tx-x) > 180 or not -240 <= ty-y <= 240:
                continue
            source, destination = by_key.get(key), by_key.get(other)
            if source and source.space == 'inside' and destination and source.owner != destination.owner:
                if destination.space == 'inside':
                    continue
                container = next((r for r in surfaces if r.key == source.owner and r.kind == 'window'), None)
                if container and container.left < tx < container.right and container.top < ty < container.bottom:
                    continue
            step = None
            if key == other and abs(ty-y) < 1:
                blocked = any(r.solid and not overlaps(x-width/2, y-height, width, height, r)
                              and r.left < max(x, tx)+width/2 and r.right > min(x, tx)-width/2
                              and r.top < y-.5 and r.bottom > y-height+.5 for r in ledges)
                if not blocked:
                    step = Step('walk', other, tx, ty)
                    extra = abs(tx-x)/28
            elif abs(ty-y) <= 240:
                velocity = jump_velocity(tx-x, ty-y)
                if velocity and clear_arc(x, y, tx, ty, velocity, ledges, width, height, ceiling):
                    step = Step('jump', other, tx, ty, *velocity)
                    extra = 1.0+abs(tx-x)/100+abs(ty-y)/100
                # Climb only a side of a solid; no climbing arbitrary air.
                elif -200 <= ty-y < -30:
                    r = next((r for r in ledges if r.key == other), None)
                    if r and r.solid and min(abs(x+width/2-r.left), abs(x-width/2-r.right)) <= 12 and r.bottom >= y:
                        edge = r.left if x < r.left else r.right
                        step = Step('climb', other, edge, ty)
                        extra = abs(ty-y)/28+1
            if step and cost+extra < distance.get(j, float('inf')):
                distance[j] = cost+extra
                parent[j] = (index, step)
                heapq.heappush(queue, (cost+extra, j))
    return []


def plan_climb_route(start_x, start_feet, start_key, ledges, width, height,
                     floor, left, right, ceiling):
    """Find an accessible object through the same multi-surface graph."""
    candidates = sorted((r for r in ledges if r.key != start_key),
                        key=lambda r: (r.top, abs((r.left+r.right)/2-start_x)))
    for target in candidates[:8]:
        route = plan_route(start_x, start_feet, start_key, target.key, ledges,
                           width, height, floor, left, right, ceiling)
        if route:
            return route
    return []


def integrate(x, y, vx, vy, dt, width, height, solids):
    """Small swept steps prevent tunnelling through sides and undersides."""
    count = max(1, math.ceil(dt*120), math.ceil((abs(vx)+abs(vy))*dt/4))
    landed, hit = None, False
    step = dt/count
    for _ in range(count):
        nx = x+vx*step
        for r in solids:
            if not r.solid or not (y+height > r.top+.5 and y < r.bottom-.5):
                continue
            if vx > 0 and x+width <= r.left+.5 and nx+width > r.left:
                nx, vx, hit = r.left-width, -vx*.2, True
            elif vx < 0 and x >= r.right-.5 and nx < r.right:
                nx, vx, hit = r.right, -vx*.2, True
        x = nx
        vy += GRAVITY*step
        ny = y+vy*step
        for r in solids:
            if not r.solid or not (x+width > r.left+.5 and x < r.right-.5):
                continue
            if vy < 0 and y >= r.bottom-.5 and ny < r.bottom:
                ny, vy, hit = r.bottom, abs(vy)*.15, True
            elif vy >= 0 and y+height <= r.top+.5 and ny+height >= r.top:
                ny, vy, landed = r.top-height, 0, r.key
                break
        y = ny
        if landed is not None:
            break
    return x, y, vx, vy, landed, hit
