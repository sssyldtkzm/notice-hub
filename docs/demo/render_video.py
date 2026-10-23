from pathlib import Path
import json, math, subprocess, wave, os, shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
R=Path(__file__).resolve().parent;FF=os.environ.get('FFMPEG') or shutil.which('ffmpeg')
if not FF: raise RuntimeError('Set FFMPEG or install ffmpeg on PATH')
scenes=json.loads((R/'scenes.json').read_text(encoding='utf-8-sig'));scenes[0]['label']='群消息整理助手'
W,H,FPS=720,1280,24
font=lambda size,bold=False:ImageFont.truetype('C:/Windows/Fonts/'+('msyhbd.ttc' if bold else 'msyh.ttc'),size)
fonts={n:font(n) for n in (18,20,23,25,27,30,38,48,52,58)};bold={n:font(n,True) for n in (25,30,38,48,52,58)}
ink='#214f40';muted='#657c6d';orange='#b46743'
for i,s in enumerate(scenes):
 subprocess.run([FF,'-y','-v','error','-i',str(R/f'voice-{i}.wav'),'-af','atempo=1.20','-ar','48000','-ac','1','-c:a','pcm_s16le',str(R/f'voice-fast-{i}.wav')],check=True)
 with wave.open(str(R/f'voice-fast-{i}.wav'),'rb') as f:a=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
 peak=max(.05,float(np.max(np.abs(a))));a=a/peak*.66;s['audio']=a;s['duration']=max(5.4,len(a)/48000+.8)
 s['frames']=round(s['duration']*FPS);s['duration']=s['frames']/FPS
 s['shots']=[Image.open(R/s[k]).convert('RGB') for k in ('image','image2') if s.get(k)]
total=sum(s['duration'] for s in scenes);N=round(total*48000);mix=np.zeros(N,dtype=np.float32);start=0
for s in scenes:
 at=round((start+.25)*48000);a=s['audio'];mix[at:at+len(a)]+=a;start+=s['duration']
t=np.arange(N)/48000
# Original, quiet major-seventh bed; no third-party music.
chords=[(130.81,164.81,196,246.94),(110,130.81,164.81,196),(87.31,110,130.81,164.81),(98,123.47,146.83,196)]
for k in range(math.ceil(total/4)):
 idx=(t>=k*4)&(t<(k+1)*4);local=t[idx]-k*4;env=np.minimum(local/.25,1)*np.minimum((4-local)/.4,1)
 for hz in chords[k%4]:mix[idx]+=.009*np.sin(2*np.pi*hz*local)*env
 for beat in range(8):
  tick=local-beat*.5;env2=np.where(tick>=0,np.exp(-np.maximum(tick,0)*7),0);mix[idx]+=.006*np.sin(2*np.pi*chords[k%4][beat%4]*4*local)*env2
mix*=np.minimum(t/.5,1)*np.minimum((total-t)/.65,1);mix=np.clip(mix,-.98,.98)
with wave.open(str(R/'soundtrack.wav'),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(48000);f.writeframes((mix*32767).astype('<i2').tobytes())
base=Image.new('RGB',(W,H),'#f3f5ec');d=ImageDraw.Draw(base);d.ellipse((380,-200,1050,470),fill='#dce8d9');d.ellipse((-350,800,260,1400),fill='#e4ebd9');base=base.filter(ImageFilter.GaussianBlur(18))
def text_center(d,txt,y,f,fill=ink):
 box=d.textbbox((0,0),txt,font=f);d.text(((W-(box[2]-box[0]))/2,y),txt,font=f,fill=fill)
def wrap(text,f,maxw):
 lines=[];line=''
 for ch in text:
  if ImageDraw.Draw(base).textlength(line+ch,font=f)>maxw and ch not in '，。！？、；：':lines.append(line);line=ch
  else:line+=ch
 if line:lines.append(line)
 return lines

def frame(si,progress):
 s=scenes[si];im=base.copy();dr=ImageDraw.Draw(im);dr.text((44,30),'群务台',font=bold[25],fill=ink);dr.text((482,36),'虚构数据演示',font=fonts[18],fill=muted)
 for j,line in enumerate(s['title'].split('\n')):text_center(dr,line,85+j*67,bold[52])
 text_center(dr,s['subtitle'],230,fonts[23],muted)
 if not s['shots']:
  cards=[('微积分课程群','第二次作业已发布，请按时提交。'),('班级通知群','提醒：明晚 22:00 前交作业。'),('学院活动群','下周五，将开展卫生大检查。')]
  for k,(name,msg) in enumerate(cards):
   off=int(24*max(0,1-progress*5+k*.18));y=390+k*170+off
   dr.rounded_rectangle((58,y,662,y+136),radius=18,fill='white',outline='#d3dfd1',width=2)
   dr.text((85,y+20),name,font=bold[25],fill=ink);dr.text((85,y+69),msg,font=fonts[23],fill=muted)
  text_center(dr,'不用再从聊天记录里，反复找。',970,fonts[30])
 else:
  shot=s['shots'][1 if len(s['shots'])>1 and progress>.48 else 0]
  # Gentle movement keeps a readable, faithful UI demonstration.
  phonew=420;screenw=396;screenh=round(screenw*shot.height/shot.width);ph=screenh+30;x=(W-phonew)//2;y=278
  shadow=Image.new('RGBA',(W,H));sd=ImageDraw.Draw(shadow);sd.rounded_rectangle((x-4,y+13,x+phonew+5,y+ph+20),radius=31,fill=(23,59,42,48));im=Image.alpha_composite(im.convert('RGBA'),shadow.filter(ImageFilter.GaussianBlur(15)))
  dr=ImageDraw.Draw(im);dr.rounded_rectangle((x,y,x+phonew,y+ph),radius=28,fill='#193a30');resized=shot.resize((screenw,screenh),Image.Resampling.LANCZOS);mask=Image.new('L',resized.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,screenw,screenh),radius=17,fill=255);im.paste(resized,(x+12,y+15),mask)
  dr=ImageDraw.Draw(im)
 dr.rounded_rectangle((70,1154,650,1233),radius=14,fill='#214f40')
 lines=wrap(s['voice'],fonts[23],534)
 for j,line in enumerate(lines[:2]):text_center(dr,line,1163+j*31,fonts[23],'#ffffff')
 text_center(dr,'个人工具 · 需电脑运行服务 · 手机连接后查看',1248,fonts[18],muted)
 # Persistent progress bar and scene marker.
 dr.text((46,1106),s['label'],font=fonts[20],fill=ink)
 dr.rounded_rectangle((46,1085,674,1090),radius=3,fill='#d2ded0');before=sum(x['duration'] for x in scenes[:si]);ratio=(before+progress*s['duration'])/total;dr.rounded_rectangle((46,1085,46+int(628*ratio),1090),radius=3,fill=ink)
 # Quick fade-in at scene boundaries.
 fade=min(1,progress*s['duration']/.28)
 if fade<1:im=Image.blend(base.convert('RGBA'),im.convert('RGBA'),fade)
 return im.convert('RGB')
output=R/'qunwutai-xuanchuan.mp4'
cmd=[FF,'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-i',str(R/'soundtrack.wav'),'-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart','-shortest',str(output)]
proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
try:
 for si,s in enumerate(scenes):
  still=frame(si,.3);second=frame(si,.7) if len(s['shots'])>1 else still
  for n in range(s['frames']):
   progress=n/max(1,s['frames']-1);im=still.copy() if progress<.44 else second.copy()
   if len(s['shots'])>1 and .44<=progress<=.52:im=Image.blend(still,second,(progress-.44)/.08)
   dr=ImageDraw.Draw(im);dr.rounded_rectangle((46,1085,674,1090),radius=3,fill='#d2ded0');ratio=(sum(x['duration'] for x in scenes[:si])+progress*s['duration'])/total;dr.rounded_rectangle((46,1085,46+int(628*ratio),1090),radius=3,fill=ink)
   fade=min(1,progress*s['duration']/.28)
   if fade<1:im=Image.blend(base,im,fade)
   proc.stdin.write(im.tobytes())
  frame(si,.6).save(R/f'preview-{si}.jpg',quality=90);print(f'Scene {si+1}/{len(scenes)} rendered',flush=True)
finally:proc.stdin.close()
if proc.wait():raise RuntimeError('video encoding failed')
summary={'file':str(output),'seconds':round(total,2),'width':W,'height':H,'fps':FPS,'size_mb':round(output.stat().st_size/1024/1024,2),'private_data':False}
(R/'video-info.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)
# Editable narration and scene timings for future revisions.
(R/'wenan.txt').write_text('\n\n'.join(s['title'].replace('\n',' ')+'\n'+s['voice'] for s in scenes),encoding='utf-8')
