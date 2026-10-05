"""World (room) points -> Kimodo canonical frame for the seated desk clips.
Canonical: the SOMA Hips root at the origin, facing +Z (towards the desk); SOMA metres. World: room.html's metres, floor
y = 0.16, desk towards -Z. The rig's scale s = 0.949 (Tripo / SOMA leg length) and its ankle sits 2.9 cm lower than
SOMA's scaled ankle (retarget.mjs compensates), so world y = s * canon_y + 0.16 - 0.029."""
S, FLOOR, DY = 0.949, 0.16, -0.029
ANCHOR = (-1.13, -0.49)           # world xz of the canonical origin (SOMA Hips root): the chair centre line, 5 cm behind the seat centre at k = 0.375
def c(wx, wy, wz, anchor=ANCHOR):
    return [round(-(wx - anchor[0]) / S, 4), round((wy - FLOOR - DY) / S, 4), round(-(wz - anchor[1]) / S, 4)]
def w(cx, cy, cz, anchor=ANCHOR):
    return [anchor[0] - cx * S, cy * S + FLOOR + DY, anchor[1] - cz * S]
KB_L, KB_R = (-1.185, 1.045, -0.885), (-1.015, 1.045, -0.885)        # wrists over ASDF / JKL (keytops 1.012, home row z -0.975)
MOUSE = (-0.736, 1.030, -0.895)                                      # wrist behind the mouse (room.html MOUSE_AT)
HIPS_Y = 0.79                                                        # SOMA Hips root seated on the 0.52 m seat (thighs on the cushion, not in it)

import math
def cy(wx, wy, wz, psi, anchor=ANCHOR):
    """c() for a chair swivelled by psi (rad, + = to his left): the world offset turned back into the desk-facing frame."""
    dx, dz = wx - anchor[0], wz - anchor[1]
    x = dx * math.cos(psi) - dz * math.sin(psi); z = dx * math.sin(psi) + dz * math.cos(psi)
    return c(anchor[0] + x, wy, anchor[1] + z, anchor)
