"""Human joint display, deliberately distinct from robot target coordinates."""
import math

import cv2
import numpy as np

COLORS={'Right':(110,245,110),'Left':(255,190,90)}


def draw_retarget_status(image, preview):
    height = image.shape[0]
    display = cv2.copyMakeBorder(image, 0, 56, 0, 0, cv2.BORDER_CONSTANT, value=(18, 23, 20))
    angles = preview["preview_motor_angles_rad"]
    if angles is None:
        detail = "No joint target: " + preview["reason"].replace("_", " ")
    else:
        joints = ("base", "shoulder", "elbow", "wrist pitch")
        detail = "   ".join(
            f"{motor} {joint} {math.degrees(angle):+.1f} deg"
            for joint, (motor, angle) in zip(joints, angles.items())
        )
    for row, label in enumerate(("ROBOT ARM SIMULATION | N: recenter", detail), start=1):
        cv2.putText(display, label, (10, height + 22 * row), cv2.FONT_HERSHEY_SIMPLEX,
                    .51, (220, 235, 220), 1, cv2.LINE_AA)
    return display


def pixel(point,width,height):
    return int((1-point['image_x'])*(width-1)),int(point['image_y']*(height-1))


def skeleton(image,frame,labels=False,muted=False):
    h,w=image.shape[:2]
    for side,color in COLORS.items():
        color=(95,100,95) if muted else color
        names=[side+'_'+j for j in ('Shoulder','Elbow','Wrist')]
        for a,b in zip(names,names[1:]):
            p,q=frame['points'][a],frame['points'][b]
            if p['visible'] and q['visible']:
                cv2.line(image,pixel(p,w,h),pixel(q,w,h),color,1 if muted else 3,cv2.LINE_AA)
        for name in names:
            p=frame['points'][name]
            if p['visible']:
                xy=pixel(p,w,h)
                cv2.circle(image,xy,6,color if p['valid'] else (90,140,255),-1,cv2.LINE_AA)
                if labels:
                    source_mark=' [hand]' if p.get('landmark_source')=='hand_wrist' else ''
                    cv2.putText(image,name.replace('_',' ')+source_mark,(max(0,xy[0]-20),max(45,xy[1]-10)),
                                cv2.FONT_HERSHEY_SIMPLEX,.43,color,1,cv2.LINE_AA)


def draw_human_arm_overlay(image,frame,fps,show_stabilized=True):
    # Framing aid: no guessed points or depth are drawn outside the image.
    h,w=image.shape[:2]
    cv2.rectangle(image,(int(.08*w),int(.08*h)),(int(.92*w),int(.92*h)),(85,90,85),1)
    filtered=frame.get('stabilized') if show_stabilized and frame.get('stabilized',{}).get('settings',{}).get('smoothing_ms',0)>0 else None
    if filtered:
        skeleton(image,frame,muted=True)
        skeleton(image,filtered,labels=True)
    else:
        skeleton(image,frame,labels=True)
    n=sum(p['visible'] for name,p in frame['points'].items() if name.startswith('Right'))
    cv2.rectangle(image,(0,0),(image.shape[1],32),(20,25,20),-1)
    cv2.putText(image,f'HUMAN ARM | {"FILTERED" if filtered else "RAW"} view | {n}/3 visible | {fps:.0f} FPS | V: toggle',
                (10,22),cv2.FONT_HERSHEY_SIMPLEX,.49,(220,245,220),1,cv2.LINE_AA)
    guidance=frame.get('capture_guidance',{})
    message=guidance.get('message','')
    cv2.rectangle(image,(0,h-31),(w,h),(20,25,20),-1)
    color=(100,240,100) if guidance.get('code') in ('ready','hand_assisted') else (80,195,255)
    cv2.putText(image,message,(8,h-11),cv2.FONT_HERSHEY_SIMPLEX,.43,color,1,cv2.LINE_AA)


def draw_human_arm_depth(image,frame,show_stabilized=True):
    # Fixed design canvas keeps labels readable when recordings use small input frames.
    h,w=image.shape[:2]
    canvas=cv2.resize(image,(640,480))
    filtered=frame.get('stabilized') if show_stabilized and frame.get('stabilized',{}).get('settings',{}).get('smoothing_ms',0)>0 else None
    skeleton(canvas,frame,muted=bool(filtered))
    if filtered:
        skeleton(canvas,filtered)
    cv2.rectangle(canvas,(0,0),(640,370),(18,23,20),-1)
    def label(s,y,color=(220,235,220),size=.48):
        cv2.putText(canvas,s,(12,y),cv2.FONT_HERSHEY_SIMPLEX,size,color,1,cv2.LINE_AA)
    label('HUMAN ARM MEASUREMENTS | NOT ROBOT TARGETS',23,(90,235,255),.57)
    quality=frame.get('quality',{})
    if quality.get('ready'):
        availability=f"Right depth 3/3: {quality['depth_complete_percent']:.0f}% / last {quality['observed_span_ms']/1000:.1f}s"
    else:
        availability='Right depth availability: warming up'
    label(availability+' | RAW XYZ metres',47,size=.43)
    for side,start in (('Right',75),('Left',220)):
        arm=frame['arms'][side]
        valid=sum(frame['points'][side+'_'+j]['valid'] for j in ('Shoulder','Elbow','Wrist'))
        label(f'{side} arm: sensor depth {valid}/3   Joint       X         Y         Z',start,COLORS[side],.43)
        for row,name in enumerate(('Shoulder','Elbow','Wrist')):
            p=frame['points'][side+'_'+name]
            coords='   '.join('--' if p[k] is None else f'{p[k]:+.3f}' for k in ('X_m','Y_m','Z_m'))
            mark=' [hand]' if p.get('landmark_source')=='hand_wrist' else ''
            label(f'{name:8s}  {coords}'+mark,start+24+row*22,COLORS[side])
        if arm['valid']:
            filtered_arm=frame.get('stabilized',{}).get('arms',{}).get(side,{})
            view_angle=filtered_arm.get('elbow_flexion_deg') if filtered_arm.get('valid') else None
            smoothed='--' if view_angle is None else f'{view_angle:.1f}'
            label(f"Elbow raw: {arm['elbow_flexion_deg']:.1f} | filtered: {smoothed} deg",start+94,COLORS[side],.45)
            label(f"Upper/forearm surface lengths: {arm['upper_arm_m']:.3f} / {arm['forearm_m']:.3f} m",start+115,size=.43)
        else:
            reasons=','.join(dict.fromkeys(frame['points'][side+'_'+j]['reason'] for j in ('Shoulder','Elbow','Wrist') if not frame['points'][side+'_'+j]['valid']))
            label('No 3D angle: '+(reasons or arm['reason']),start+94,(100,180,255),.42)
    label(frame.get('capture_guidance',{}).get('message','Keep full arm in view.'),390,(90,210,255),.43)
    label('Camera sees clothing/skin surface; no anatomical accuracy claim.',413,size=.44)
    ms=frame.get('stabilized',{}).get('settings',{}).get('smoothing_ms',0)
    label(f'V: raw/filtered skeleton | filter {ms:g}ms | grey=raw trace',436,size=.44)
    label('No motor commands. No O/F/W/Space calibration required.',459,size=.44)
    image[:]=cv2.resize(canvas,(w,h))
