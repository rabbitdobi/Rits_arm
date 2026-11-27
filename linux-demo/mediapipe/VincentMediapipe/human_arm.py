"""Human arm image landmarks and same-frame D455 measurements, never motor targets."""
import math
import copy
from arm_stabilizer import ArmStabilizer
from arm_quality import ArmQuality
import numpy as np
from realsense_source import sample_point

ARM_JOINTS = {'Right_Shoulder':12, 'Right_Elbow':14, 'Right_Wrist':16,
              'Left_Shoulder':11, 'Left_Elbow':13, 'Left_Wrist':15}
HUMAN_ARM_FIELDS = ['timestamp_ms','joint','visible','visibility','presence','image_x','image_y',
                    'valid','reason','X_m','Y_m','Z_m','valid_fraction','spread_m',
                    'predicted_image_x','predicted_image_y','image_issue','landmark_source','pose_reason','handedness_score']


def visible(p, threshold=.6):
    values = [getattr(p,k,None) for k in ('x','y','visibility','presence')]
    return (all(isinstance(v,(int,float)) and math.isfinite(v) for v in values)
            and 0 <= p.x < 1 and 0 <= p.y < 1 and p.visibility >= threshold and p.presence >= threshold)


def select_pose(result):
    candidates=[]
    for i,pts in enumerate(result.pose_landmarks):
        if len(pts) != 33:
            continue
        usable=[pts[j] for j in (11,12,13,14,15,16,23,24) if visible(pts[j])]
        if len(usable)<3:
            continue
        xs=[p.x for p in usable];ys=[p.y for p in usable]
        extent=max(max(xs)-min(xs),max(ys)-min(ys))
        candidates.append((extent*extent*sum(p.visibility for p in usable)/len(usable),i))
    return max(candidates)[1] if candidates else None


def arm_geometry(points,side):
    result=dict(valid=False,reason='joint_depth_unavailable',elbow_flexion_deg=None,
                upper_arm_m=None,forearm_m=None,wrist_relative_shoulder_m=None,hand_assisted_joints=0)
    joints=[points[side+'_'+name] for name in ('Shoulder','Elbow','Wrist')]
    if not all(p['valid'] for p in joints):
        return result
    s,e,w=[np.array([p[k] for k in ('X_m','Y_m','Z_m')]) for p in joints]
    upper,fore=np.linalg.norm(e-s),np.linalg.norm(w-e)
    if not (.1 <= upper <= .65 and .1 <= fore <= .65):
        return dict(result,reason='implausible_segment_length')
    cosine=float(np.dot(s-e,w-e)/(upper*fore))
    return dict(valid=True,reason='ok',elbow_flexion_deg=180-math.degrees(math.acos(max(-1.,min(1.,cosine)))),
                upper_arm_m=float(upper),forearm_m=float(fore),wrist_relative_shoulder_m=(w-s).tolist(),
                hand_assisted_joints=sum(p['landmark_source']=='hand_wrist' for p in joints))


def hand_wrists_from_result(result):
    wrists=[]
    for i,pts in enumerate(result.hand_landmarks):
        if len(pts)!=21 or not result.handedness[i]:
            continue
        category=max(result.handedness[i],key=lambda c:c.score)
        wrists.append(dict(side=category.category_name,score=float(category.score),x=float(pts[0].x),y=float(pts[0].y)))
    return wrists


def validated_hand_wrists(wrists):
    return [dict(side=q['side'],score=float(q['score']),x=float(q['x']),y=float(q['y'])) for q in wrists
            if q.get('side') in ('Right','Left')
            and all(isinstance(q.get(k),(int,float)) and math.isfinite(q[k]) for k in ('score','x','y'))
            and 0<=q['score']<=1]


def assist_hand_wrists(points,wrists,raw,scale,deproject):
    h,w=raw.shape
    for side in ('Right','Left'):
        p=points[side+'_Wrist'];elbow=points[side+'_Elbow'];shoulder=points[side+'_Shoulder']
        x,y=p['predicted_image_x'],p['predicted_image_y']
        # Do not rescue hidden/outside or weakly identified body joints. The hand
        # model supplies its own wrist landmark, never a substitute depth value.
        if (p['valid'] or not elbow['visible'] or not shoulder['visible']
                or x is None or y is None or not (0<=x<1 and 0<=y<1)
                or p['visibility'] is None or p['visibility']<.6
                or p['presence'] is None or p['presence']<.2):
            continue
        forearm_pixels=math.hypot((elbow['image_x']-x)*w,(elbow['image_y']-y)*h)
        radius=min(20.,max(4.,.2*forearm_pixels))
        matches=[]
        for q in wrists:
            values=[q.get(k) for k in ('score','x','y')]
            if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in values):
                continue
            if (q.get('side')!=side or q['score']<.8 or not (0<=q['x']<1 and 0<=q['y']<1)
                    or math.hypot((q['x']-x)*w,(q['y']-y)*h)>radius):
                continue
            matches.append(q)
        if len(matches)!=1:
            continue
        q=matches[0]
        sampled=sample_point(raw,scale,q['x'],q['y'],deproject)
        if sampled['valid']:
            p.update({k:v for k,v in sampled.items() if k not in ('pixel_x','pixel_y')})
            p.update(visible=True,image_x=q['x'],image_y=q['y'],landmark_source='hand_wrist',handedness_score=q['score'])


def capture_guidance(points,arms):
    wrist=points['Right_Wrist']
    x,y=wrist['predicted_image_x'],wrist['predicted_image_y']
    if arms['Right']['valid'] and wrist['landmark_source']=='hand_wrist':
        code,message='hand_assisted','Right arm 3D: hand-assisted wrist, current sensor depth'
    elif wrist['image_issue']=='out_of_frame':
        code,message='wrist_out_of_frame','Move back / bring right wrist inside the frame'
    elif x is not None and y is not None and min(x,y,1-x,1-y)<.08:
        code,message='wrist_near_edge','Right wrist near edge: move back or bring arm inward'
    elif wrist['image_issue']=='low_visibility':
        code,message='wrist_occluded','Right wrist uncertain/occluded: separate arm from body'
    elif not wrist['visible']:
        code,message='wrist_uncertain','Keep shoulder, elbow and wrist fully visible; move slowly'
    elif (wrist['reason'] in ('center_hole','sparse_depth')
          and points['Right_Elbow']['valid'] and 0<points['Right_Elbow']['Z_m']<.55):
        return dict(code='wrist_may_be_too_close',
                    message='Wrist may be too close: move the whole arm farther back',
                    inferred=True,reference_joint='Right_Elbow',reference_z_m=points['Right_Elbow']['Z_m'],
                    caution_threshold_m=.55)
    elif wrist['reason'] in ('center_hole','sparse_depth','depth_edge'):
        code,message='wrist_depth_missing','Wrist depth missing: turn arm slightly; keep lenses clear'
    elif arms['Right']['valid']:
        code,message='ready','Right arm 3D available (surface measurements)'
    elif wrist['reason']=='no_sensor_depth':
        code,message='no_sensor_depth','2D only: a depth source is required for sensor XYZ'
    else:
        code,message='arm_incomplete','Right arm incomplete: keep shoulder and elbow visible'
    return dict(code=code,message=message,inferred=False)


class HumanArmTracker:
    def __init__(self,smoothing_ms=80):
        self.timestamp=None
        self.stabilizer=ArmStabilizer(smoothing_ms)
        self.quality=ArmQuality()

    def update(self,landmarks,timestamp_ms,raw=None,scale=None,deproject=None,hand_wrists=None):
        t=float(timestamp_ms)
        if not math.isfinite(t) or self.timestamp is not None and t<=self.timestamp:
            raise ValueError('Human arm timestamps must increase')
        self.timestamp=t
        if landmarks is not None and len(landmarks)!=33:
            landmarks=None
        points={}
        for name,index in ARM_JOINTS.items():
            p=None if landmarks is None else landmarks[index]
            ok=p is not None and visible(p)
            point=dict(visible=ok,visibility=None,presence=None,image_x=None,image_y=None,
                       valid=False,reason='pose_unavailable' if p is None else 'low_confidence_or_outside',
                       X_m=None,Y_m=None,Z_m=None,valid_fraction=0.,spread_m=None,
                       predicted_image_x=None,predicted_image_y=None,image_issue='pose_unavailable',
                       landmark_source='pose',pose_reason=None,handedness_score=None)
            if p is not None:
                x,y=getattr(p,'x',None),getattr(p,'y',None)
                finite_xy=all(isinstance(v,(int,float)) and math.isfinite(v) for v in (x,y))
                if finite_xy:
                    point.update(predicted_image_x=float(x),predicted_image_y=float(y))
                visibility=getattr(p,'visibility',None)
                presence=getattr(p,'presence',None)
                if not finite_xy:
                    issue='invalid_landmark'
                elif not (0<=x<1 and 0<=y<1):
                    issue='out_of_frame'
                elif not isinstance(visibility,(int,float)) or not math.isfinite(visibility) or visibility<.6:
                    issue='low_visibility'
                elif not isinstance(presence,(int,float)) or not math.isfinite(presence) or presence<.6:
                    issue='low_presence'
                else:
                    issue='ok'
                point['image_issue']=issue
                for key in ('visibility','presence'):
                    value=getattr(p,key,None)
                    point[key]=float(value) if isinstance(value,(int,float)) and math.isfinite(value) else None
            if ok:
                point.update(image_x=float(p.x),image_y=float(p.y),reason='no_sensor_depth')
                if raw is not None and deproject is not None:
                    sampled=sample_point(raw,scale,p.x,p.y,deproject)
                    point.update({k:v for k,v in sampled.items() if k not in ('pixel_x','pixel_y')})
            point['pose_reason']=point['reason']
            points[name]=point
        if raw is not None and deproject is not None:
            assist_hand_wrists(points,validated_hand_wrists(hand_wrists or []),raw,scale,deproject)
        arms={side:arm_geometry(points,side) for side in ('Right','Left')}
        frame=dict(schema_version=1,timestamp_ms=t,units='m',coordinate_frame='d455_color_optical' if raw is not None else None,
                    source='pose_image_landmarks_and_aligned_depth' if raw is not None else 'pose_image_landmarks_only',
                    tracked=any(p['visible'] for p in points.values()),points=points,
                    arms=arms,capture_guidance=capture_guidance(points,arms),
                    hand_wrist_candidates=validated_hand_wrists(hand_wrists or []),
                    hardware_enabled=False)
        frame['stabilized']=stabilize_frame(frame,self.stabilizer)
        frame['quality']=self.quality.update(frame,t)
        return frame


def stabilize_frame(frame,stabilizer):
    inputs=copy.deepcopy(frame['points'])
    # Do not smooth an anatomically rejected raw configuration into a usable arm.
    for side,arm in frame['arms'].items():
        if arm['reason']=='implausible_segment_length':
            for joint in ('Shoulder','Elbow','Wrist'):
                inputs[side+'_'+joint].update(valid=False,X_m=None,Y_m=None,Z_m=None)
    filtered=stabilizer.update(inputs,frame['timestamp_ms'])
    arms={side:arm_geometry(filtered['points'],side) for side in ('Right','Left')}
    for side,raw_arm in frame['arms'].items():
        if not raw_arm['valid']:
            arms[side].update(valid=False,reason='raw_geometry_unavailable',elbow_flexion_deg=None,
                              upper_arm_m=None,forearm_m=None,wrist_relative_shoulder_m=None)
    filtered['arms']=arms
    return filtered


def write_human_arm_csv(writer,frame):
    for name,point in frame['points'].items():
        writer.writerow(dict(timestamp_ms=frame['timestamp_ms'],joint=name,**point))
