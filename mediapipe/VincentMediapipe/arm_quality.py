"""Observed right-arm sample availability, not physical accuracy or confidence."""
from collections import deque
import math


class ArmQuality:
    def __init__(self):
        self.samples=deque()
        self.timestamp=None
        self.session=dict(frames=0,visible_complete_frames=0,depth_complete_frames=0,geometry_valid_frames=0)

    def update(self,frame,timestamp_ms):
        t=float(timestamp_ms)
        if not math.isfinite(t) or self.timestamp is not None and t<=self.timestamp:
            raise ValueError('Quality timestamps must increase')
        if self.timestamp is not None and t-self.timestamp>250:
            self.samples.clear()
        self.timestamp=t
        points=[frame['points']['Right_'+j] for j in ('Shoulder','Elbow','Wrist')]
        visible=all(p['visible'] for p in points)
        depth=all(p['valid'] for p in points)
        geometry=bool(frame['arms']['Right']['valid'])
        self.samples.append((t,visible,depth,geometry))
        while self.samples and t-self.samples[0][0]>=2000:
            self.samples.popleft()
        self.session['frames']+=1
        for key,value in (('visible_complete_frames',visible),('depth_complete_frames',depth),('geometry_valid_frames',geometry)):
            self.session[key]+=int(value)
        count=len(self.samples);duration=t-self.samples[0][0]
        ready=count>=10 and duration>=1000
        return dict(kind='sample_availability_not_accuracy',window_ms=2000,observed_span_ms=duration,
                    frames=count,ready=ready,
                    depth_complete_percent=100*sum(s[2] for s in self.samples)/count if ready else None,
                    geometry_valid_percent=100*sum(s[3] for s in self.samples)/count if ready else None,
                    session=self.session.copy())
