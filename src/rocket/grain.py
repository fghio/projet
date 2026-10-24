import numpy as np

class BatesGrain:
    def __init__(
        self,
        segments,
        outer_diameter,
        core_diameter,
        segment_length,
        inhibited_ends = False
    ):
        # cylindrical segments with a circular port; the outer surface is bonded to the case
        self.segments = int(segments)
        self.outer_diameter = outer_diameter
        self.core_diameter = core_diameter
        self.segment_length = segment_length
        self.inhibited_ends = bool(inhibited_ends)

    def web(
        self
    ):
        # burnout: the port reaches the case or (burning ends) the segment length is consumed
        radial = (self.outer_diameter - self.core_diameter) / 2
        if self.inhibited_ends:
            return radial
        return min(radial, self.segment_length / 2)

    def geometry(
        self,
        x
    ):
        # port diameter and segment length after a burnt web x
        d = self.core_diameter + 2*x
        L = self.segment_length if self.inhibited_ends else self.segment_length - 2*x
        return d, L

    def burnArea(
        self,
        x
    ):
        d, L = self.geometry(x)
        area = np.pi * d * L
        if not self.inhibited_ends:
            area += 2 * np.pi/4 * (self.outer_diameter**2 - d**2)
        return self.segments * area

    def portArea(
        self,
        x
    ):
        d, _ = self.geometry(x)
        return np.pi * d**2 / 4

    def volume(
        self,
        x = 0
    ):
        # propellant volume left after a burnt web x
        d, L = self.geometry(x)
        return self.segments * np.pi/4 * (self.outer_diameter**2 - d**2) * L


class EndBurnerLayer:
    def __init__(
        self,
        diameter,
        length
    ):
        # one layer of a cigarette (end-burning) grain: only the face towards the nozzle burns,
        # the lateral surface is bonded to the case, so the burn area stays constant
        self.diameter = diameter
        self.length = length

    def web(
        self
    ):
        return self.length

    def burnArea(
        self,
        x
    ):
        return np.pi * self.diameter**2 / 4

    def volume(
        self,
        x = 0
    ):
        return np.pi * self.diameter**2 / 4 * (self.length - x)


def layerBlocks(grain):
    """(name, block) of the layers of a cigarette grain, from the nozzle side (layer1) to the head end"""
    names = [k for k, v in grain.items() if isinstance(v, dict) and k.startswith("layer") and k[5:].isdigit()]
    return [(k, grain[k]) for k in sorted(names, key=lambda k: int(k[5:]))]
