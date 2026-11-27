"""Compare raw and filtered visualization on an unchanged dense human-arm log."""
import argparse
import copy
import json
from pathlib import Path
import numpy as np
from arm_stabilizer import ArmStabilizer
from human_arm import stabilize_frame


def distribution(values):
    if not values:
        return dict(count=0,median=None,p95=None)
    return dict(count=len(values),median=float(np.median(values)),p95=float(np.quantile(values,.95)))


def compare_window(frames,name,start,end):
    window=[f for f in frames if start*1000<=f['timestamp_ms']<end*1000]
    common=[f for f in window if f['arms']['Right']['valid'] and f['stabilized']['arms']['Right']['valid']]
    result=dict(name=name,start_s=start,end_s=end,frames=len(window),shared_geometry_frames=len(common),
                raw_geometry_frames=sum(f['arms']['Right']['valid'] for f in window),
                filtered_geometry_frames=sum(f['stabilized']['arms']['Right']['valid'] for f in window))
    for label in ('raw','filtered'):
        angles=[(f if label=='raw' else f['stabilized'])['arms']['Right']['elbow_flexion_deg'] for f in common]
        result[label]=dict(angle_std_deg=float(np.std(angles)) if angles else None,
                           angle_central90_deg=np.quantile(angles,[.05,.95]).tolist() if angles else None)
        steps=[];switch_steps=[]
        for a,b in zip(window,window[1:]):
            dt=b['timestamp_ms']-a['timestamp_ms']
            ra,rb=a['points']['Right_Wrist'],b['points']['Right_Wrist']
            fa,fb=a['stabilized']['points']['Right_Wrist'],b['stabilized']['points']['Right_Wrist']
            if dt>100 or not all(p['valid'] for p in (ra,rb,fa,fb)):
                continue
            p,q=(ra,rb) if label=='raw' else (fa,fb)
            step=float(np.linalg.norm(np.array([p[k] for k in ('X_m','Y_m','Z_m')])-np.array([q[k] for k in ('X_m','Y_m','Z_m')]))*1000)
            steps.append(step)
            if ra.get('landmark_source')!=rb.get('landmark_source'):
                switch_steps.append(step)
        result[label]['wrist_adjacent_step_mm']=distribution(steps)
        result[label]['wrist_source_switch_step_mm']=distribution(switch_steps)
    return result


def run(args):
    original=[json.loads(line) for line in args.log.read_text().splitlines() if line.strip()]
    stabilizer=ArmStabilizer(args.smoothing_ms)
    frames=[]
    for raw in original:
        frame=copy.deepcopy(raw)
        frame['stabilized']=stabilize_frame(frame,stabilizer)
        frames.append(frame)
    report=dict(source=str(args.log.resolve()),frames=len(frames),settings=stabilizer.settings,
                note='Same raw log, sources and time intervals. Filtered visualization is not increased measurement accuracy. Windows inferred from video; human motion is not separated from detector noise.',
                windows=[compare_window(frames,name,float(start),float(end)) for name,start,end in (w.split(':') for w in args.window)])
    if args.transition:
        start,end=map(float,args.transition.split(':'))
        first=report['windows'][0]
        second=report['windows'][1]
        vals=[]
        for w in (first,second):
            subset=[f['arms']['Right']['elbow_flexion_deg'] for f in frames if w['start_s']*1000<=f['timestamp_ms']<w['end_s']*1000 and f['arms']['Right']['valid']]
            vals.append(float(np.median(subset)))
        midpoint=sum(vals)/2
        crossings={}
        for name in ('raw','filtered'):
            candidates=[]
            for f in frames:
                arm=(f if name=='raw' else f['stabilized'])['arms']['Right']
                if start*1000<=f['timestamp_ms']<end*1000 and arm['valid']:
                    if (arm['elbow_flexion_deg']-midpoint)*(vals[1]-vals[0])>=0:
                        candidates.append(f['timestamp_ms'])
            crossings[name]=candidates[0] if candidates else None
        report['transition']=dict(start_s=start,end_s=end,midpoint_deg=midpoint,crossing_ms=crossings,
                                  extra_crossing_delay_ms=crossings['filtered']-crossings['raw'] if all(v is not None for v in crossings.values()) else None)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    with (args.output/'filtered.jsonl').open('x') as f:
        for frame in frames:f.write(json.dumps(frame,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,len(report['windows']),figsize=(6*len(report['windows']),6),squeeze=False)
    for col,w in enumerate(report['windows']):
        window=[f for f in frames if w['start_s']*1000<=f['timestamp_ms']<w['end_s']*1000]
        for label,color in (('raw','#b35b45'),('filtered','#167e9b')):
            x=[];angle=[];wx=[]
            for f in window:
                data=f if label=='raw' else f['stabilized']
                x.append(f['timestamp_ms']/1000)
                a=data['arms']['Right'];p=data['points']['Right_Wrist']
                angle.append(a['elbow_flexion_deg'] if a['valid'] else np.nan)
                wx.append(p['X_m']*100 if p['valid'] else np.nan)
            axes[0,col].plot(x,angle,label=label,color=color,linewidth=1)
            axes[1,col].plot(x,wx,label=label,color=color,linewidth=1)
        axes[0,col].set_title(f"{w['name']}: {w['start_s']:g}-{w['end_s']:g}s")
        axes[0,col].set_ylabel('Elbow flexion (degrees)')
        axes[1,col].set_ylabel('Camera wrist X (cm)')
        axes[1,col].set_xlabel('Capture time (s)')
        for ax in axes[:,col]:ax.grid(alpha=.2);ax.legend()
    fig.suptitle('Raw vs filtered visualization — no ground-truth accuracy measurement')
    fig.tight_layout();fig.savefig(args.output/'comparison.png',dpi=150);plt.close(fig)
    if args.samples:
        import cv2
        from human_arm_view import draw_human_arm_overlay,draw_human_arm_depth
        from recording import VideoRecorder
        by_time={f['timestamp_ms']:f for f in frames}
        paths=sorted(args.samples.glob('*.json'))
        recorder=VideoRecorder(args.output/'preview.mp4',1,(1280,480))
        count=0
        try:
            for path in paths:
                saved=json.loads(path.read_text());frame=by_time.get(saved['timestamp_ms'])
                if frame is None:continue
                with np.load(path.with_suffix('.npz')) as arrays:rgb=arrays['color_bgr'].copy();depth=arrays['depth_z16'].copy()
                image=cv2.flip(rgb,1);draw_human_arm_overlay(image,frame,0)
                view=cv2.flip(cv2.applyColorMap(cv2.convertScaleAbs(depth,alpha=.04),cv2.COLORMAP_JET),1)
                draw_human_arm_depth(view,frame)
                image=np.hstack((image,view))
                cv2.putText(image,'RECORDED: one sample per second',(10,52),cv2.FONT_HERSHEY_SIMPLEX,.43,(50,220,255),1,cv2.LINE_AA)
                recorder.write(image,count*1000)
                if count==len(paths)//2:cv2.imwrite(str(args.output/'preview.png'),image)
                count+=1
        finally:recorder.close()
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--log',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--samples',type=Path)
    p.add_argument('--smoothing-ms',type=float,default=80.)
    p.add_argument('--window',action='append',required=True,help='name:start_seconds:end_seconds')
    p.add_argument('--transition',help='start_seconds:end_seconds for midpoint delay check')
    run(p.parse_args())
