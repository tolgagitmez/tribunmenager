"""Independent moving-window calibration, only in the private CI display."""
import json
import time
import tkinter as tk


def main():
    root=tk.Tk()
    root.title('Tribun capture calibration')
    root.geometry('1280x720+0+152')
    root.overrideredirect(True)
    canvas=tk.Canvas(root,width=1280,height=720,background='#101010',highlightthickness=0)
    canvas.pack()
    rect=canvas.create_rectangle(0,200,160,360,fill='white',outline='white')
    label=canvas.create_text(640,100,text='',fill='white',font=('Sans',32))
    root.update()
    started=time.monotonic()
    times=[]

    def tick():
        t=time.monotonic()
        i=len(times)
        if t-started>=6:
            print(json.dumps(dict(start=times[0],end=t,drawnFrames=len(times))),flush=True)
            root.destroy()
            return
        x=(i*23)%1100
        canvas.coords(rect,x,200,x+160,360)
        canvas.itemconfigure(label,text=str(i))
        root.update_idletasks()
        times.append(time.monotonic())
        root.after(33,tick)

    tick()
    root.mainloop()


if __name__=='__main__':
    main()
