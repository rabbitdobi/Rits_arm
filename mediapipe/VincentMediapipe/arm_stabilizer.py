"""Time-based visualization filtering; never changes raw measurements or fills loss."""
import copy
import math
import numpy as np


class ArmStabilizer:
    def __init__(self,smoothing_ms=80):
        ms=float(smoothing_ms)
        if not math.isfinite(ms) or ms<0:
            raise ValueError('Arm smoothing must be finite and nonnegative')
        self.settings=dict(smoothing_ms=ms,switch_smoothing_ms=max(ms,180.) if ms else 0.,
                           switch_window_ms=240.,gap_reset_ms=250.)
        self.timestamp=None
        self.state={}

    def update(self,points,timestamp_ms):
        t=float(timestamp_ms)
        if not math.isfinite(t) or self.timestamp is not None and t<=self.timestamp:
            raise ValueError('Stabilizer timestamps must increase')
        dt=0. if self.timestamp is None else t-self.timestamp
        gap=dt>self.settings['gap_reset_ms']
        if gap:
            self.state.clear()
        self.timestamp=t
        self.state={name:s for name,s in self.state.items() if name in points}
        result=copy.deepcopy(points)
        for name,p in result.items():
            xyz=[p.get(k) for k in ('X_m','Y_m','Z_m')]
            good=bool(p.get('valid')) and all(isinstance(v,(int,float)) and math.isfinite(v) for v in xyz)
            xy=[p.get(k) for k in ('image_x','image_y')]
            good_xy=all(isinstance(v,(int,float)) and math.isfinite(v) for v in xy)
            if not good_xy:
                p.update(image_x=None,image_y=None,visible=False)
            if not good:
                self.state.pop(name,None)
                p.update(valid=False,X_m=None,Y_m=None,Z_m=None)
                p['stabilization']=dict(alpha=None,source_changed=False,reset='invalid_current_sample')
                continue
            current=np.array(xyz,dtype=float)
            source=p.get('landmark_source','pose')
            old=self.state.get(name)
            changed=old is not None and old['source']!=source
            switch_until=t+self.settings['switch_window_ms'] if changed else old['switch_until'] if old is not None else -1.
            tau=(self.settings['switch_smoothing_ms'] if t<switch_until else self.settings['smoothing_ms'])
            alpha=1. if old is None or tau==0 else -math.expm1(-dt/tau)
            filtered=current if old is None else old['xyz']+alpha*(current-old['xyz'])
            current_xy=np.array(xy,dtype=float) if good_xy else None
            if old is not None and current_xy is not None and old['xy'] is not None:
                current_xy=old['xy']+alpha*(current_xy-old['xy'])
            p.update(dict(zip(('X_m','Y_m','Z_m'),map(float,filtered))))
            if current_xy is not None:
                p.update(image_x=float(current_xy[0]),image_y=float(current_xy[1]))
            p['stabilization']=dict(alpha=alpha,tau_ms=tau,source_changed=changed,
                                    reset='gap' if gap else 'first_or_reacquired' if old is None else None)
            self.state[name]=dict(xyz=filtered,xy=current_xy,source=source,switch_until=switch_until)
        return dict(kind='filtered_visualization',points=result,settings=self.settings.copy(),
                    hardware_enabled=False)
