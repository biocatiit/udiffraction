#! /usr/bin/python
# Raul Barrea January 2012
# Small fix for changed Keithley PVs
# Mono2 default

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import time
from builtins import range, str
from io import open
from tkinter import Button, Radiobutton, Menubutton, Checkbutton
from tkinter import Label, Frame, Menu, Entry
from tkinter import SUNKEN, W, E, X, TOP, LEFT, RIGHT
from tkinter import StringVar, DoubleVar, IntVar
from tkinter.filedialog import LoadFileDialog
from tkinter.filedialog import askopenfilename

try:
    import Mp as mp
except:
    print('MP is not supported')

import numpy as np
import tables
from epics import PV, Motor

Version = '0.9.9-ccd beta'  # HDF save format, CCD trigger, MCA, Newport stages
ccdfudge = 10  # seconds
dxpfudge = 1
fudge = 0.800
dmswitch = 0
permit = 0
abort = 0
reason = 'not initialized'
cROI = 1
ROI = 1
HDFext = 'hdf'

PV_BL = '18ID:'
Mono = PV_BL + 'MO2:E:ActPos'

KEITH = ['k428-10', 'k428-11', 'k428-12', 'k428-13']
KGAIN = ':totalgain'
k_gain_pv = [PV(PV_BL + KEITH[0] + KGAIN), PV(PV_BL + KEITH[1] + KGAIN),
             PV(PV_BL + KEITH[2] + KGAIN), PV(PV_BL + KEITH[3] + KGAIN)]

PA = 'PA:'
ASTAT = 'FES_PS2_OPENED_LS'
DSTAT = 'I46:'
xi_pv = PV('S:SRcurrentAI')
# Energy = PV(Mono)
XIANO = PV_BL + 'bi0:ch7'
XIANC = PV_BL + 'bi0:ch6'
SHCTL = PV_BL + 'bo0:ch6'

# Shutter was upgraded by APS on Sept. 2013. Shutter PVs were changed.
sh_a_pv = PV(PA + PV_BL + ASTAT)  # New PV in FMap_dataInitial.txt
# sh_d0_pv = PV(PA+PV_BL+DSTAT+'00')
# sh_d1_pv = PV(PA+PV_BL+DSTAT+'01')
# sh_d2_pv = PV(PA+PV_BL+DSTAT+'02')
# sh_d3_pv = PV(PA+PV_BL+DSTAT+'03')
sh_d0_pv = PV(PA + PV_BL + 'SDS_MS1_SS1_OPEN_LS')
sh_d1_pv = PV(PA + PV_BL + 'SDS_MS1_SS1_CLSD_LS')
sh_d2_pv = PV(PA + PV_BL + 'SDS_MS2_SS2_OPEN_LS')
sh_d3_pv = PV(PA + PV_BL + 'SDS_MS2_SS2_CLSD_LS')

sh_no_pv = PV(XIANO)
sh_nc_pv = PV(XIANC)
sh_pv = PV(SHCTL)

# MAR = PV_BL+'marCCD:det1:'
# MAR = 'Mar165_B:cam1:'
MAR = 'Mar165:cam1:'
mar_acq_pv = PV(MAR + 'Acquire')
mar_int_pv = PV(MAR + 'AcquireTime')
mar_write_pv = PV(MAR + 'WriteFile')

mxPV = 'none'
xi = 0.
xf = 0
xstep = 0
mtPV = 'none'
ti = 0.
tf = 0
tstep = 0
myPV = 'none'
yi = 0.
yf = 0
ystep = 0
MAXMOTORS = 40

dark = []
JOERGER = 'scaler2'
JSTART = '.CNT'
J1SHOT = '.CONT'
JDATA = '.S'  # followed by a channel number
JSETTM = '.TP'
JETIME = '.T'
# One probably doesn't want to write to these five PVs, but I place them here
# as a reminder that they should be checked.
JDIR = '.D'  # followed by a channel number  Should be 0
JDLY = '.DLY'  # Should be 0
JFREQ = '.FREQ'  # Should be 1e7
JGATE = '.G'  # followed by a channel number  Should be 0
JPRE = '.PR'  # followed by a channel number  Should be 0

MAX_CHANNELS_PV = PV(PV_BL + JOERGER + '.NCH')

j_start_pv = PV(PV_BL + JOERGER + JSTART)
j_set_time_pv = PV(PV_BL + JOERGER + JSETTM)
j_el_time_pv = PV(PV_BL + JOERGER + JETIME)
j_set_cts_pv = PV(PV_BL + JOERGER + JPRE + '1')
j_el_cts_pv = PV(PV_BL + JOERGER + JDATA + '1')

# Set up MCA PVs
global mca_erasestart_pv, mca_stop_pv, mca_data_pv
global nMCA, mca_live_pv, mca_real_pv, mca_dead_pv
global nROI, mca_ROIn_pv, mca_ROId_pv, mca_ROIl_pv, mca_ROIh_pv
global NoXRF
NoXRF = 1  # one means don't save XRF


def pv_connected(pv):
    status = pv.connected
    if not status:
        print('\033[91mERROR: \033[0mProcess Variable \033[91m' + pv.pvname + '\033[0m is not connected')
    return status


def get_mxdir():
    """Gets the top level install directory for MX."""
    try:
        mxdir = os.environ["MXDIR"]
    except:
        mxdir = "/opt/mx"  # This is the default location.

    return mxdir


def get_mpdir():
    """Construct the name of the Mp modules directory."""
    mxdir = get_mxdir()

    mp_modules_dir = os.path.join(mxdir, "lib", "mp")
    mp_modules_dir = os.path.normpath(mp_modules_dir)

    return mp_modules_dir


def set_mppath():
    """Puts the mp directory in the system path, if it isn't already."""
    os.environ['PATH']

    mp_dir = get_mpdir()

    if mp_dir not in os.environ['PATH']:
        os.environ["PATH"] = mp_dir + os.pathsep + os.environ["PATH"]
    if mp_dir not in sys.path:
        sys.path.append(mp_dir)


class ShutterStatusPanel(Frame):
    def __init__(self, master):
        Frame.__init__(self, master)
        Label(self, text="Shutter Status:  ").grid(row=0, column=0)
        self.a = Label(self, text="A", bg='green')
        self.a.grid(row=0, column=1)
        self.d = Label(self, text="D", bg='green')
        self.d.grid(row=0, column=2)
        self.no = Label(self, text="NO", bg='green')
        self.no.grid(row=0, column=3)
        self.nc = Label(self, text="NC", bg='green')
        self.nc.grid(row=0, column=4)
        self.shutterscan()

    def shutter_pv_connected(self):
        return pv_connected(sh_d0_pv) and \
               pv_connected(sh_d1_pv) and \
               pv_connected(sh_d2_pv) and \
               pv_connected(sh_d3_pv)

    def shutterscan(self):
        global shstat
        shstat = 1
        if pv_connected(sh_a_pv):
            self.a.config(bg='green')
        else:
            self.a.config(bg='red')
            shstat = 0

        if self.shutter_pv_connected() and (
                sh_d0_pv.get() + sh_d2_pv.get() == 2 and sh_d1_pv.get() + sh_d3_pv.get() == 0):
            self.d.config(bg='green')
        else:
            self.d.config(bg='red')
            shstat = 0

        if pv_connected(sh_no_pv):
            self.no.config(bg='green')
        else:
            self.no.config(bg='red')
            shstat = 0

        if pv_connected(sh_nc_pv):
            self.nc.config(bg='green')
        else:
            self.nc.config(bg='red')
            shstat = 0


class MotorEntry(Frame):
    def __init__(self, master, text):
        Frame.__init__(self, master)
        self.go = 0
        self.mPV = StringVar()
        self.mPVVAL = StringVar()
        self.mPVVAL.set("Motor Name")
        self.mPVPOS = StringVar()
        self.mi = DoubleVar()
        self.mf = DoubleVar()
        self.center = DoubleVar()
        self.width = DoubleVar()
        self.mstep = DoubleVar()
        self.use = IntVar()
        self.use_epics = IntVar()
        self.useb = Checkbutton(self, fg="blue", relief=SUNKEN, text="Use", variable=self.use)
        self.useb.grid(row=0, column=0, rowspan=2)
        self.useb.select()
        self.label = Label(self, bd=1, relief=SUNKEN, width=32, fg="gold", bg="black")
        self.label.config(textvariable=self.mPVVAL)
        self.label.grid(row=0, column=1, columnspan=3)
        Button(self, width=4, text=" Initial: ", command=self.ifrompv).grid(row=0, column=4)
        self.CenterTE = Entry(self, bg='yellow', textvariable=self.center, width=6)
        self.InitTE = Entry(self, bg='cyan', textvariable=self.mi, width=6)
        self.InitTE.bind("<Return>", self.if2cw)
        self.InitTE.grid(row=0, column=5)
        Button(self, width=4, text="Final: ", command=self.ffrompv).grid(row=0, column=6)
        self.FinalTE = Entry(self, bg="cyan", textvariable=self.mf, width=6)
        self.FinalTE.bind("<Return>", self.if2cw)
        self.FinalTE.grid(row=0, column=7)
        Label(self, text=" Step: ").grid(row=0, column=8, rowspan=1)
        Entry(self, bg='cyan', textvariable=self.mstep, width=6).grid(row=0, column=9, rowspan=1)

        Label(self, bg='grey', text=text, width=18).grid(row=1, column=1, sticky=W)
        Checkbutton(self, text="epics", variable=self.use_epics).grid(row=1, column=2, sticky=E)
        self.mPVTE = Entry(self, bg='cyan', textvariable=self.mPV, width=4)
        self.mPVTE.bind("<Return>", self.zap)
        self.mPVTE.grid(row=1, column=3, sticky=W)
        # Button(self, width=4, text=" Center: ", command=self.cfrompv).grid(row=1,column=4)
        # self.CenterTE = Entry(self,bg='yellow',textvariable=self.center, width=6)
        # self.CenterTE.bind("<Return>",self.cw2if)
        # self.CenterTE.grid(row=1,column=5)
        # Label(self, text=" Width: ").grid(row=1,column=6)
        # self.WidthTE = Entry(self,bg='yellow',textvariable=self.width, width=6)
        # self.WidthTE.bind("<Return>",self.cw2if)
        # self.WidthTE.grid(row=1,column=7)

        # Add Radio Button to select different type of Motor. - By Chen
        #  Label(self, text=PV_BL+'e:m').grid(row=1, column=2, sticky=E)
        # self.motorText = StringVar()
        # Label(self, textvariable=self.motorText).grid(row=1, column=2, sticky=E)
        # End Chen
        # Add Radio Button to select different type of Motor. - By Chen

        self.motorType = IntVar()
        self.stepperRB = Radiobutton(self, text="Stepper", variable=self.motorType, value=0)
        self.stepperRB.grid(row=2, column=0, columnspan=2)
        self.newportRB = Radiobutton(self, text="Newport", variable=self.motorType, value=1)
        self.newportRB.grid(row=2, column=2, columnspan=2)

        # if (self.motorType.get() == 0):
        #     self.motorText.set(PV_BL + 'e:m')
        #     motorTypeSelected = 0
        #
        # else:
        #     self.motorText.set(PV_BL + 'n:np')
        #     motorTypeSelected = 1

        # End Chen

        Label(self, text="Current Position:  ").grid(row=1, column=4, columnspan=3, sticky=E)
        self.mpos = Label(self, bd=1, relief=SUNKEN, width=14, fg="gold", bg="black")
        self.mpos.config(textvariable=self.mPVPOS)
        self.mpos.grid(row=1, column=7, columnspan=2)
        Label(self, width=50).grid(row=3, columnspan=7)

    # Add Radio Button to select different type of Motor. - By Chen
    # def selMotType(self):
    #     if (self.motorType.get() == 0):
    #         self.motorText.set(PV_BL + 'e:m')
    #         motorTypeSelected = 0
    #
    #     else:
    #         self.motorText.set(PV_BL + 'n:np')
    #         motorTypeSelected = 1

    # End Chen

    def ifrompv(self):
        self.zap(None)
        if (self.go == 1):
            self.mi.set(round(self.motorPV.position, 4))
            writestat('Start Position Selected')
            self.if2cw(None)
        else:
            writestat('No Motor Selected', color='pink')
            return

    def ffrompv(self):
        self.zap(None)
        if (self.go == 1):
            self.mf.set(round(self.motorPV.position, 4))
            writestat('End Position Selected')
            self.if2cw(None)
        else:
            writestat('No Motor Selected', color='pink')
            return

    def cfrompv(self):
        self.zap(None)
        if (self.go == 1):
            self.center.set(round(self.motorPV.position, 4))
            writestat('Center Position Selected')
            self.cw2if(None)
        else:
            writestat('No Motor Selected', color='pink')
            return

    def browse(self):
        print("I don't do anything yet")

    def zap(self, event):
        # Set the flag red
        self.go = 0
        # If the motor isn't being used, then set the flag green, but disable it.
        if (self.use.get() and len(self.mPV.get()) != 0):
            if (self.motorType.get() == 0):
                self.PV = PV_BL + "e:m" + self.mPV.get()
                # Call Motor at this point.
                self.motorPV = Motor(self.PV)
                self.mPVVAL.set(self.motorPV.description)
                self.mPVPOS.set(round(self.motorPV.get_position(readback=1), 4))
                self.label.config(fg="green")
                self.go = 1  # Everything is good as far as getting motor values is concerned.
            else:
                self.PV = PV_BL + "n:np" + self.mPV.get()
                # Call Motor at this point.
                if not hasattr(self, 'motorPV'):
                    self.motorPV = MotorControl(self.mPV.get(), use_epic=self.use_epics.get(), mx_db=mx_database)
                    self.mPVVAL.set(self.motorPV.description)
                    self.mPVPOS.set(round(self.motorPV.position, 4))
                self.label.config(fg="green")
                self.go = 1  # Everything is good as far as getting motor values is concerned.
        else:
            self.go = 1
            self.motorPV = None
            self.motor = 'Disabled'
            self.mPVVAL.set(self.motor)
            self.label.config(fg="pink")

        mw.update()

    def if2cw(self, event):
        i = self.mi.get()
        f = self.mf.get()
        self.center.set((f + i) / 2.0)
        self.width.set(f - i)

    def cw2if(self, event):
        c = self.center.get()
        w = self.width.get()
        self.mi.set(c - (w / 2.0))
        self.mf.set(c + (w / 2.0))


class MotorPanel(Frame):
    def __init__(self, master):
        Frame.__init__(self, master)
        self.mx = MotorEntry(self, "(1) MOTOR X")
        self.mx.pack(side=TOP)
        self.mt = MotorEntry(self, "(2) MOTOR Z")
        self.mt.pack(side=TOP)
        self.my = MotorEntry(self, "(3) MOTOR Y")
        self.my.pack(side=TOP)


class MCAPanel(Frame):
    def __init__(self, master):
        Frame.__init__(self, master)
        self.intt = DoubleVar()
        self.MCAv = IntVar()
        self.tch = IntVar()
        self.tch.set(15)
        Label(self, text=" Combined XRD/XRF? (Default Y)").grid(row=0, column=0)
        Radiobutton(self, text="No XRF", variable=self.MCAv, value=1).grid(row=1, column=0)
        Radiobutton(self, text="XRD/XRF", variable=self.MCAv, value=0).grid(row=1, column=1)
        NoXRF = self.MCAv.get()
        print('NoXRF=', NoXRF)
        # Entry(self,bg='cyan',textvariable=self.intt, width=6).grid(row=0,column=2)
        # Label(self, text="s").grid(row=0,column=3)
        Label(self, text="CCD Trigger Channel (Default = 15) ").grid(row=2, column=0)
        Entry(self, bg='cyan', textvariable=self.tch, width=6).grid(row=2, column=2, rowspan=2)
        Label(self, text="   Joerger Channels: ").grid(row=0, column=4, rowspan=1)
        self.jcb = []
        self.j = []

        if pv_connected(MAX_CHANNELS_PV):
            max_channels = MAX_CHANNELS_PV.get()
            for i in range(max_channels // 2):
                self.j.append(IntVar())
                self.jcb.append(Checkbutton(self, relief=SUNKEN, text=str(i + 1), variable=self.j[i]))
                self.jcb[i].grid(row=0, column=5 + i)
            for i in range((max_channels // 2), max_channels):
                self.j.append(IntVar())
                self.jcb.append(Checkbutton(self, relief=SUNKEN, text=str(i + 1), variable=self.j[i]))
                self.jcb[i].grid(row=1, column=5 + i - (max_channels // 2))
            self.jcb[2].select()
            self.jcb[3].select()
            self.jcb[4].select()
            self.jcb[5].select()


class FilenamePanel(Frame):
    def __init__(self, master, text):
        Frame.__init__(self, master)
        Label(self, text=text).pack(side=LEFT)
        self.filename = StringVar()
        self.fileidx = StringVar()
        self.fileidx.set('0001')
        Entry(self, width=55, textvariable=self.filename).pack(side=LEFT, fill=X)
        Label(self, text='Index:').pack(side=LEFT)
        Entry(self, width=5, textvariable=self.fileidx).pack(side=LEFT, fill=X)
        Button(self, text="Browse...", command=self.browse).pack(side=RIGHT)

    def browse(self):
        file = LoadFileDialog(self).go(pattern='*')
        if file:
            sep = '_'
            self.filename.set(sep.join(file.split('.')[0].split(sep)[0:-1]))
            self.fileidx.set(file.split('.')[0].split(sep)[-1])


class MainWindow(Frame):
    def __init__(self, master):
        Frame.__init__(self, master)
        self.statustext = StringVar()
        self.statustext.set("Awaiting Scan Parameters")
        self.progresstext = StringVar()
        self.progresstext.set("Mode: Initial State")
        self.pausestate = IntVar()
        self.pausestate.set(1)
        self.pausetext = StringVar()
        self.pausetext.set("Pause ||")
        self.mb = Menubutton(self, text="Parameter Files", relief="groove")
        self.mb.menu = Menu(self.mb, tearoff=0)
        self.mb["menu"] = self.mb.menu
        self.mb.menu.add_command(label="Save Scan Parameters to...", command=self.psave)
        self.mb.menu.add_command(label="Append Scan Parameters to...", command=self.pappend)
        self.mb.menu.add_command(label="Load Scan Parameters from...", command=self.pload)
        self.mb.menu.add_separator()
        self.mb.menu.add_command(label="Quit", command=self.harikiri)
        #  self.mb.grid(columnspan=3,sticky=W)
        self.mb.grid(row=0, sticky=W)
        Label(self, text=Version).grid(row=0, column=2, sticky=E)
        Label(self, text="Stepper Motor Scan for Microdiffraction").grid(row=0, column=1)
        self.shutter = ShutterStatusPanel(self)
        self.shutter.grid(columnspan=3)
        self.m = MotorPanel(self)
        self.m.grid(columnspan=3)
        self.mca = MCAPanel(self)
        self.mca.grid(columnspan=3)
        self.f = FilenamePanel(self, "Filename: ")
        self.f.grid(columnspan=3)
        Button(self, text="Take Dark",
               activebackground="black", activeforeground="white",
               command=self.take_dark).grid(row=5, column=0, sticky=W)
        self.go = Button(self, bg='black', fg="green", text="Go! ->",
                         activebackground="green", activeforeground="black",
                         command=self.gogo)
        self.go.grid(row=5, column=1, sticky=W)
        self.pauseb = Button(self, bg="black", fg="pink",
                             activebackground="red", activeforeground="blue",
                             command=self.pausebutton)
        self.pauseb.config(textvariable=self.pausetext)
        self.pauseb.grid(row=5, column=1, sticky=E)
        self.abortb = Button(self, text="ABORT", bg="black", fg="red",
                             activebackground="red", activeforeground="black",
                             command=self.abortbutton)
        self.abortb.grid(row=5, column=2, sticky=E)
        self.go.bind("<Enter>", self.update_motors)
        self.statusbox = Label(self, bd=1, relief=SUNKEN, width=90, fg="gold", bg="black")
        self.statusbox.config(textvariable=self.statustext)
        self.statusbox.grid(columnspan=3)
        self.progressbox = Label(self, bd=1, relief=SUNKEN, width=90, fg="gold", bg="black")
        self.progressbox.config(textvariable=self.progresstext)
        self.progressbox.grid(columnspan=3)

        ####################################################################
        # If you change this structure, you MUST change the program Version!
        ####################################################################
        self.pfstruc = [['myPV', self.m.my.mPV],
                        ['yi', self.m.my.mi],
                        ['yf', self.m.my.mf],
                        ['ystep', self.m.my.mstep],
                        ['mtPV', self.m.mt.mPV],
                        ['ti', self.m.mt.mi],
                        ['tf', self.m.mt.mf],
                        ['tstep', self.m.mt.mstep],
                        ['mxPV', self.m.mx.mPV],
                        ['xi', self.m.mx.mi],
                        ['xf', self.m.mx.mf],
                        ['xstep', self.m.mx.mstep],
                        ['CCDch', self.mca.tch],
                        ['CCDdt', self.mca.intt],
                        ['MCA', self.mca.MCAv],
                        ['MCAdt', self.mca.intt],
                        ['File', self.f.filename],
                        ['FileIdx', self.f.fileidx]]

    def psave(self, qfile=None):
        global pfile
        # the job of this command is to save all the parameters into a file for
        # future reference...
        if (qfile == None):
            pfile = askopenfilename(filetypes=[('Par File', '*.par')])
        else:
            pfile = qfile
        if pfile:
            with open(pfile, 'r+') as pfp:
                pfp.write('Version = ' + Version + '\n')
                for i in range(len(self.pfstruc)):
                    pfp.write(self.pfstruc[i][0] + ' = ' + str(self.pfstruc[i][1].get()) + '\n')

            print("Reloading ", pfile)
            self.pload(pfile)  # Loads the parameter file just saved.
            self.update()

    def pload(self, qfile=None, idex=0):
        global pfile, ROI
        # the job of this command is to reload all the parameters into the program.
        if qfile == None:
            pfile = askopenfilename(filetypes=[('Par File', '*.par')])
        else:
            pfile = qfile
        self.param = []
        with open(pfile, 'r') as pfp:
            lineno = 0
            for line in pfp:
                pdata = line.split('=')[1].split(',')
                if lineno == 0:  # This is the version string
                    print("Parameter File Version:  " + str.strip(pdata[0]))
                    self.param.append(str.strip(pdata[0]))
                else:
                    print(pdata, len(pdata))
                    ROI = len(pdata)
                    self.param.append(str.strip(pdata[idex]))
                lineno += 1

        if self.param[0] != Version:
            self.statusbox.config(fg="pink")
            self.statustext.set('Version Mismatch: ' + self.param[0] + ' != ' + Version)
            self.update()
            return
        for i in range(len(self.pfstruc)):
            self.pfstruc[i][1].set(self.param[i + 1])  # self.param[0] -> version string
        print("Regions = ", ROI)

    def pappend(self, qfile=None):
        global pfile, ROI
        # the job of this command is to reload all the parameters into the program.
        if qfile == None:
            pfile = askopenfilename(filetypes=[('Par File', '*.par')])
        else:
            pfile = qfile
        parlist = []
        with open(pfile, 'r+') as pfp:
            for line in pfp:
                pdata = line.split('=')[1].split(',')
                print(pdata, len(pdata))
                ROI = len(pdata)
                parlist.append(pdata)
            if parlist[0][0] != Version:
                self.statusbox.config(fg="pink")
                self.statustext.set('Version Mismatch: ' + parlist[0][0] + ' != ' + Version)
                self.update()
                return
            pfp.seek(0)
            pfp.write('Version = ' + Version + '\n')
            for i in range(len(self.pfstruc)):
                parlist[i + 1].append(str(self.pfstruc[i][1].get()))
                pfp.write(self.pfstruc[i][0] + ' = ')
                for j in range(len(parlist[i + 1])):
                    pfp.write(str(parlist[i + 1][j]))
                    if (j != len(parlist[i + 1]) - 1):
                        pfp.write(',')
                pfp.write('\n')
                print(self.pfstruc[i][0] + ' -> ' + str(parlist[i + 1]))

        print("Reloading ", pfile)
        self.pload(pfile)  # Loads the parameter file just saved.

        print("Regions = ", ROI)

    def harikiri(self):
        sys.exit(0)

    def pausebutton(self):
        if (self.pausestate.get() == 1):
            self.pausestate.set(0)
            self.pausetext.set("Resume ->")
            self.pauseit('User Request')
        else:
            self.pausestate.set(1)
            self.pausetext.set("Pause ||")
            self.unpauseit()

    def pauseit(self, bleh):
        global permit, reason
        permit = 0
        reason = bleh
        self.statusbox.config(fg="pink")
        self.statustext.set('Paused: ' + reason)
        self.update()

    def unpauseit(self):
        global permit
        permit = 1
        self.statusbox.config(fg="gold")
        self.statustext.set('Scan Resumed...')
        self.update()

    def abortbutton(self):
        global abort
        abort = 1
        self.statusbox.config(fg="red")
        self.statustext.set('Scan Aborted')
        self.progressbox.config(fg="gold")
        self.progresstext.set('Aborting Scan...')
        self.update()

    def update_motors(self, event):
        self.m.my.zap(None)
        self.m.mt.zap(None)
        self.m.mx.zap(None)
        self.shutter.shutterscan()

    def init_joerger(self):
        # Set up the scaler and get the list of channels to read:
        self.statusbox.config(fg="gold")
        self.statustext.set("Initializing Joerger Scaler")
        self.update()
        if (PV(PV_BL + JOERGER + JFREQ).get() != 10000000.):
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set("Joerger Frequency != 10 MHz")
            return
        if (PV(PV_BL + JOERGER + JDLY).get() != 0.):
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set("Joerger Delay != 0")
            return
        if (PV(PV_BL + JOERGER + J1SHOT).get() != 0):
            print('Joerger not in one-shot mode.... setting...')
            if (PV(PV_BL + JOERGER + J1SHOT).put(0) == None):
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Unable to set Joerger to One-Shot Mode")
                if (PV(PV_BL + JOERGER + J1SHOT).get() != 0):
                    self.go = 0
                    self.statusbox.config(fg="pink")
                    self.statustext.set("Unable to verify Joerger in One-Shot Mode")
                    return

    def take_dark(self, darktime=1.):
        global dark, shstat
        self.shutter.shutterscan()
        if (shstat):
            self.go = 0
            self.statusbox.config(fg='white')
            self.statustext.set("All X-Ray Shutters are Open")
            return
        self.init_joerger()
        if (PV(PV_BL + JOERGER + JSETTM).put(darktime) == None):
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set("Unable to set Joerger Dark Time")
            return
        if (PV(PV_BL + JOERGER + JSETTM).get() != darktime):
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set("Unable to retrieve correct Joerger Dark Time")
            return
        self.statusbox.config(fg="pink")
        self.statustext.set("Taking 10 second dark...")
        self.progressbox.config(fg="gold")
        self.progresstext.set("Mode: Joerger Dark Current Measurement")
        self.update()
        # Start the Joerger counting:
        a = j_start_pv.put(1)
        if (a == None):
            print('ERROR: Failed caput' + repr(j_start_pv.pvname))
            sys.exit(-1)
        # Wait for the specified time
        time.sleep(darktime + fudge)
        # Stop counting
        # Check to be sure the Joerger is done counting:
        while (j_start_pv.get() != 0):
            print('ERROR: Joerger not finished counting')
        # Get the data
        dark = []
        if pv_connected(MAX_CHANNELS_PV):
            for i in range(MAX_CHANNELS_PV.get()):
                dark.append(PV(PV_BL + JOERGER + JDATA + str(i + 1)).get() / 10.)
        self.statusbox.config(fg="green")
        self.statustext.set("Dark Currents Recorded")
        self.progresstext.set("Ready to begin scan")

    def gogo(self):
        global cROI, abort
        cROI = 1
        abort = 0
        self.progresstext.set("Mode: Confirming Scan Parameters")
        self.check_status()

    def check_status(self):
        global scaler, scalerPV, permit, abort, HDFext
        # This entire routine's job is to ensure everything is kosher before we
        # launch the scan.  It's a long routine. :/
        global uy, yi, yf, ystep, ut, ti, tf, tstep, ux, xi, xf, xstep, inttime

        # Set go/no-go flag green but turn it red if we find an error anywhere.
        self.go = 1
        # Check for green lights everywhere
        # You should probably check to see if the shutters are open/closed.
        # Update motor information
        print('Scanning started')
        self.m.my.zap(None)
        uy = self.m.my.use.get()
        self.m.mt.zap(None)
        ut = self.m.mt.use.get()
        self.m.mx.zap(None)
        ux = self.m.mx.use.get()
        self.statustext.set("Checking...")
        if (uy):
            if (self.m.my.go == 1):
                myPV = self.m.my.mPV.get()
            else:
                self.statusbox.config(fg="pink")
                self.statustext.set("Y Motor Problem...")
                self.go = 0
                return
        if (ut):
            if (self.m.mt.go == 1):
                mtPV = self.m.mt.mPV.get()
            else:
                self.statusbox.config(fg="pink")
                self.statustext.set("Theta Motor Problem...")
                self.go = 0
                return
        if (ux):
            if (self.m.mx.go == 1):
                mxPV = self.m.mx.mPV.get()
            else:
                self.statusbox.config(fg="pink")
                self.statustext.set("X Motor Problem...")
                self.go = 0
                return
        if (ux and ut and mxPV == mtPV):
            self.statusbox.config(fg="pink")
            self.statustext.set("X Motor Cannot be the same as Theta Motor")
            self.go = 0
            return
        if (ux and uy and mxPV == myPV):
            self.statusbox.config(fg="pink")
            self.statustext.set("X Motor Cannot be the same as Y Motor")
            self.go = 0
            return
        if (ut and uy and mtPV == myPV):
            self.statusbox.config(fg="pink")
            self.statustext.set("Theta Motor Cannot be the same as Y Motor")
            self.go = 0
            return
        # Ok, through with motor testing.  On to motor range testing.
        # Check everyone for valid answers.
        if (uy):
            try:
                yi = self.m.my.mi.get()
            except ValueError:
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Bad Value for Y Start")
                return
            try:
                yf = self.m.my.mf.get()
            except ValueError:
                self.go = 0

                self.statusbox.config(fg="pink")
                self.statustext.set("Bad Value for Y Stop")
                return
            try:
                ystep = self.m.my.mstep.get()
            except ValueError:
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Bad Value for Y Step")
                return
            if (ystep == 0.):
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Y: Zero value for Step")
                return
            elif (yf - yi == 0.):
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Y: Zero Range")
                return
        if (ut):
            try:
                ti = self.m.mt.mi.get()
            except ValueError:
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Bad Value for Theta Start")
                return
            try:
                tf = self.m.mt.mf.get()
            except ValueError:
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Bad Value for Theta Stop")
                return
            try:
                tstep = self.m.mt.mstep.get()
            except ValueError:
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Bad Value for Theta Step")
                return
            if (tstep == 0.):
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Theta: Zero value for Step")
                return
            elif (tf - ti == 0.):
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Theta: Zero Range")
                return
        if (ux):
            try:
                xi = self.m.mx.mi.get()
            except ValueError:
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Bad Value for X Start")
                return
            try:
                xf = self.m.mx.mf.get()
            except ValueError:
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Bad Value for X Stop")
                return
            try:
                xstep = self.m.mx.mstep.get()
            except ValueError:
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Bad Value for X Step")
                return
            if (xstep == 0.):
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("X: Zero value for Step")
                return
            elif (xf - xi == 0.):
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("X: Zero Range")
                return

            global mca_erasestart_pv, mca_stop_pv, mca_data_pv
            global nMCA, mca_live_pv, mca_real_pv, mca_dead_pv

            global nROI, mca_ROIn_pv, mca_ROId_pv, mca_ROIl_pv, mca_ROIh_pv

            MCA_v = 0
            MCA_R = 'dxp2:'
            MCA_D = 'mca'  # The old AIM had MCA_R='aim_adc1'
            nROI = 4
            nMCA = 1
            mca_erasestart_pv = PV(PV_BL + MCA_R + MCA_D + '1EraseStart')
            mca_stop_pv = PV(PV_BL + MCA_R + MCA_D + '1Stop')

            # Actually, the 7-element detector has ROIs 0-31 for *each* MCA
            # and the following two additional fields:
            #                                  .R#BG = 'nAvg', .R#N = 'net'

            mca_data_pv = []
            mca_live_pv = []
            mca_real_pv = []
            mca_dead_pv = []
            mca_ROIl_pv = []
            mca_ROIh_pv = []
            mca_ROIn_pv = []
            mca_ROId_pv = []
            for i in range(nMCA):
                mca_ROIl_pv.append([])
                mca_ROIh_pv.append([])
                mca_ROId_pv.append([])
                mca_ROIn_pv.append([])
                mca_data_pv.append(PV(PV_BL + MCA_R + MCA_D + repr(i + 1) + '.VAL'))
                mca_live_pv.append(PV(PV_BL + MCA_R + MCA_D + repr(i + 1) + '.ELTM'))
                mca_real_pv.append(PV(PV_BL + MCA_R + MCA_D + repr(i + 1) + '.ERTM'))
                mca_dead_pv.append(PV(PV_BL + MCA_R + MCA_D + repr(i + 1) + '.IDTIM'))
                for j in range(nROI):
                    mca_ROId_pv[i].append(PV(PV_BL + MCA_R + MCA_D + repr(i + 1) + '.R' + repr(j)))
                    mca_ROIl_pv[i].append(PV(PV_BL + MCA_R + MCA_D + repr(i + 1) + '.R' + repr(j) + 'LO'))
                    mca_ROIh_pv[i].append(PV(PV_BL + MCA_R + MCA_D + repr(i + 1) + '.R' + repr(j) + 'HI'))
                    mca_ROIn_pv[i].append(PV(PV_BL + MCA_R + MCA_D + repr(i + 1) + '.R' + repr(j) + 'NM'))

            ##For the MAR, the trigger channel is specified above.  No need to check.
            try:
                trigch = self.mca.tch.get()
            except ValueError:
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Bad Value for Trigger Channel")
                return
            if (trigch > 15 or trigch < 10):
                self.go = 0
                self.statusbox.config(fg="pink")
                self.statustext.set("Trigger Channel must be between 10 and 15")
                return
            trigPV = PV(PV_BL + 'bo0:ch' + repr(trigch))
            trigPV.put(0)

            ##The CCD time is specified in the MAR window

            self.statusbox.config(fg="gold")
            self.statustext.set("Getting Integration Time from MAR...")
            self.mca.intt.set(mar_int_pv.get())
        try:
            inttime = self.mca.intt.get()
        except ValueError:
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set("Bad Value for Integration Time")
            return
        if (inttime < 0.0):
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set("Integration Time must be positive")
            return
        self.statusbox.config(fg="white")
        self.statustext.set("Integration Time OK")
        # check Joerger Scaler
        if (len(dark) < 16):
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set("<--- Please Take Dark Currents")
            return
        self.init_joerger()
        if (PV(PV_BL + JOERGER + JSETTM).put(inttime) == None):
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set("Unable to set Joerger Integration Time")
            return
        if (PV(PV_BL + JOERGER + JSETTM).get() != inttime):
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set("Unable to retrieve correct Joerger Integration Time")
            return
        scaler = []
        scalerPV = []
        if pv_connected(MAX_CHANNELS_PV):
            for i in range(MAX_CHANNELS_PV.get()):
                if (self.mca.j[i].get() == 1):
                    scaler.append(i + 1)
                    scalerPV.append(PV(PV_BL + JOERGER + JDATA + str(i + 1)))
        nJ = len(scaler)
        # File fun
        filen = self.f.filename.get()
        fileidx = self.f.fileidx.get()
        if (filen == ''):
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set("No File Selected.")
            return
        # Does the file already exist?
        try:
            intfi = int(fileidx)
        except ValueError:
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set("File Index Error.")
            return
        while (os.path.exists(filen + '_' + fileidx + '.' + HDFext)):
            self.go = 0
            self.statusbox.config(fg="pink")
            self.statustext.set('File ' + filen + '_' + fileidx + '.' + HDFext + ' already exists.  Incrementing.')
            self.update()
            intfi += 1
            fileidx = '%4.4d' % (intfi)
            self.f.fileidx.set(fileidx)
        self.go = 1
        filename = filen + '_' + fileidx
        # Ok, write a new file and build the header...
        self.statusbox.config(fg="gold")
        self.statustext.set('Writing header to ' + filename + '.' + HDFext + '...')
        self.update()
        # fHDFhead--------------------------------------------------------------------
        zz = 'FMAP Data Set for ' + filename
        h5f = tables.open_file(filename + '.' + HDFext, mode='w', title=zz,
                               filters=tables.Filters(complevel=5))
        ginfo = h5f.create_group("/", 'header', 'Scan Information')

        a = h5f.create_array('/header', 'Date', [time.asctime()], 'Date of Data Aquisition')
        for i in range(len(KEITH)):
            a = h5f.create_array('/header', 'Keithley' + repr(i) + 'Gain', [k_gain_pv[i].get()],
                                 'Gain of Keithley Amplifier ' + repr(i) + ' (V/A)')
        # a = h5f.create_array('/header','MonochromatorEnergy',[Energy.get()],
        #      'Energy of Monochromator (keV)')
        a = h5f.create_array('/header', 'IntegrationTime', [inttime],
                             'Detector integration time (s)')
        if (ux):
            a = h5f.create_array('/header', 'Xinitial', [self.m.mx.mi.get()],
                                 'Initial X motor position (mm)')
            a = h5f.create_array('/header', 'Xstep', [self.m.mx.mstep.get()],
                                 'X motor step size (mm)')
            a = h5f.create_array('/header', 'Xfinal', [self.m.mx.mf.get()],
                                 'Final X motor position (mm)')
        if (ut):
            a = h5f.create_array('/header', 'THETAinitial', [self.m.mt.mi.get()],
                                 'Initial THETA motor position (mm)')
            a = h5f.create_array('/header', 'THETAstep', [self.m.mt.mstep.get()],
                                 'THETA motor step size (mm)')
            a = h5f.create_array('/header', 'THETAfinal', [self.m.mt.mf.get()],
                                 'Final THETA motor position (mm)')
        if (uy):
            a = h5f.create_array('/header', 'Yinitial', [self.m.my.mi.get()],
                                 'Initial Y motor position (mm)')
            a = h5f.create_array('/header', 'Ystep', [self.m.my.mstep.get()],
                                 'Y motor step size (mm)')
            a = h5f.create_array('/header', 'Yfinal', [self.m.my.mf.get()],
                                 'Final Y motor position (mm)')

        class sROIt(tables.IsDescription):
            MCAn = tables.UInt16Col(pos=1)
            LowV = tables.Int16Col(shape=(1, nROI), pos=2)
            Label = tables.StringCol(itemsize=8, shape=(1, nROI), pos=3)
            HighV = tables.Int16Col(shape=(1, nROI), pos=4)

        t = h5f.create_table('/header', 'sROI', sROIt, 'Spectral ROIs')
        t._v_attrs.MCAn = "Channel Number"
        t._v_attrs.LowV = "Spectral ROI Lowest Energy Bin"
        t._v_attrs.Label = "User Supplied Spectral ROI Label"
        t._v_attrs.HighV = "Spectral ROI Highest Energy Bin"
        sROIe = t.row

        if (NoXRF == 0):  # NoXRF==1 means no fluorescence 0 means include XRF
            for i in range(nMCA):
                templ = []
                temph = []
                tempn = []
                for j in range(nROI):
                    templ.append(mca_ROIl_pv[i][j].get())
                    tempn.append(mca_ROIn_pv[i][j].get())
                    temph.append(mca_ROIh_pv[i][j].get())

                sROIe['MCAn'] = i + 1
                sROIe['LowV'] = templ
                sROIe['Label'] = tempn
                sROIe['HighV'] = temph
                sROIe.append()

        t.flush()

        # Attributes to add:  Location (BioCAT), Detector type
        # fHDFhead--------------------------------------------------------------------
        # fHDFdata--------------------------------------------------------------------
        # Structure the HDF file for the data sets
        gdata = h5f.create_group("/", 'data', 'Scan Data')

        class voxel(tables.IsDescription):
            if (ux): pX = tables.Float32Col(pos=1)
            if (ut): pT = tables.Float32Col(pos=2)
            if (uy): pY = tables.Float32Col(pos=3)
            BeamCurrent = tables.Float32Col()
            Jchans = tables.Float32Col(shape=(1, nJ))

        class mca(tables.IsDescription):
            LiveT = tables.Float32Col(pos=1)
            RealT = tables.Float32Col(pos=2)
            DeadT = tables.Float32Col(pos=3)
            sROI = tables.Float32Col(shape=(1, nROI))
            data = tables.UInt16Col(shape=(1, 2048))

        t = h5f.create_table('/data', 'BL', voxel, 'Beam-line Parameters')
        t._v_attrs.BeamCurrent = "Synchrotron Beam Current (mA)"
        jchandesc = 'Joerger Scaler Channels:  '
        for i in range(nJ):
            jchandesc += 'Jchan' + repr(scaler[i])
        t._v_attrs.Jchans = jchandesc
        if (ux): t._v_attrs.pX = 'X motor position (mm)'
        if (ut): t._v_attrs.pT = 'THETA motor position (mm)'
        if (uy): t._v_attrs.pY = 'Y motor position (mm)'

        for i in range(nMCA):
            q = h5f.create_table('/data', 'MCA' + repr(i + 1), mca, 'Data from MCA' + repr(i + 1))
            q._v_attrs.LiveT = "Live Time (s)"
            q._v_attrs.RealT = "Real Time (s)"
            q._v_attrs.DeadT = "Dead Time (s)"
            q._v_attrs.sROI = "Spectral ROI data (counts)"
            q._v_attrs.data = "MCA" + repr(i + 1) + " Data (counts)"

        if (self.go == 1):
            # all is good...
            permit = 1
            self.statusbox.config(fg="gold")
            self.statustext.set("Calling Scan Routine...")
            self.update()
            # Call procedure here
            self.scan(self.m.my.motorPV, yi, yf, ystep,
                      self.m.mt.motorPV, ti, tf, tstep,
                      self.m.mx.motorPV, xi, xf, xstep,
                      inttime, trigPV, h5f)
        else:
            self.statusbox.config(fg="pink")
            self.statustext.set("Undetermined Error. Halting.")
            self.update()

    def scan(self, yPV, yi, yf, ystep,
             tPV, ti, tf, tstep,
             xPV, xi, xf, xstep,
             inttime, trigPV, h5f):
        global permit, abort, ROI, cROI, dmswitch
        global TotalXsteps, TotalTsteps, TotalYsteps, uy, ut, ux
        count = 0
        begin_time = 0.
        cycle_time = 0.
        yns = 0
        tns = 0
        xns = 0
        self.statustext.set("Beginning Scan...")
        self.progresstext.set("Beginning Scan...")
        # calculate number of steps and direction for each motor move:
        if (uy):
            print("Y Motor = ")
            print("yi = " + '%.3f' % yi)
            print("yf = " + '%.3f' % yf)
            print("ystep = " + '%.3f' % ystep)
            dir = 1
            delta = yf - yi
            if (delta < 0): dir = -1
            ystep = dir * abs(ystep)
            yns = int(round(abs((delta) / ystep)))
            ylastpos = yPV.position

            # This section is for motor timing  #
            yv = yPV.slew_speed
            yvb = yPV.base_speed
            yta = yPV.acceleration
            ytrap = (yv + yvb) * yta
            if (yv == yvb or yta == 0.):
                yq = -1
            else:
                yq = (yv - yvb) / yta
            #####################################

        TotalYsteps = yns + 1

        if (ut):
            print("T Motor = ")
            print("ti = " + '%.3f' % ti)
            print("tf = " + '%.3f' % tf)
            print("tstep = " + '%.3f' % tstep)
            dir = 1
            delta = tf - ti
            if (delta < 0): dir = -1
            tstep = dir * abs(tstep)
            tns = int(round(abs((delta) / tstep)))
            tlastpos = tPV.position

            # This section is for motor timing  #
            tv = tPV.slew_speed
            tvb = tPV.base_speed
            tta = tPV.acceleration
            ttrap = (tv + tvb) * tta
            if (tv == tvb or tta == 0.):
                tq = -1
            else:
                tq = (tv - tvb) / tta
            #####################################

        TotalTsteps = tns + 1

        if (ux):
            print("X Motor = ")
            print("xi = " + '%.3f' % xi)
            print("xf = " + '%.3f' % xf)
            print("xstep = " + '%.3f' % xstep)
            dir = 1
            delta = xf - xi
            if (delta < 0): dir = -1
            xstep = dir * abs(xstep)
            xns = int(round(abs((delta) / xstep)))
            xlastpos = xPV.position

            # This section is for motor timing  #
            xv = xPV.slew_speed
            xvb = xPV.base_speed
            xta = xPV.acceleration
            xtrap = (xv + xvb) * xta
            if (xv == xvb or xta == 0.):
                xq = -1
            else:
                xq = (xv - xvb) / xta
            #####################################

        TotalXsteps = xns + 1

        npts = (yns + 1) * (tns + 1) * (xns + 1)
        print("inttime = " + '%.3f' % inttime)

        # Open the file
        self.statustext.set("Scanning...")
        # set up outer (Y) loop:
        for y in range(yns + 1):
            # If used, move motor
            if (uy):
                ypos = yi + (y * ystep)
                ymove = abs(ypos - ylastpos)
                yPV.move(ypos)
                # self.move_motor_debug(yPV, 'Y', ypos, ymove, yq, yv, yvb, yta, ytrap)
                ylastpos = ypos
            # set up inner (Theta) loop:
            for t in range(tns + 1):
                # If used, move motor
                if (ut):
                    tpos = ti + (t * tstep)
                    tmove = abs(tpos - tlastpos)
                    tPV.move(tpos)
                    # self.move_motor_debug(tPV, 'Z', tpos, tmove, tq, tv, tvb, tta, ttrap)
                    tlastpos = tpos
                # set up inner (X) loop:
                for x in range(xns + 1):
                    # If used, move motor
                    print('================================ START')
                    if (ux):
                        xpos = xi + (x * xstep)
                        xmove = abs(xpos - xlastpos)
                        xPV.move(xpos)
                        # self.move_motor_debug(xPV, 'X', xpos, xmove, xq, xv, xvb, xta, xtrap)
                        xlastpos = xpos
                    #
                    ###Inside the data loop.... Try not to fill it with too much crap.
                    #
                    # Calculate ETA
                    count += 1
                    cycle_time_last = cycle_time
                    cycle_time = time.time()
                    tt = cycle_time - begin_time
                    ct = cycle_time - cycle_time_last
                    if (count != 1):
                        at = tt / float(count - 1)
                        print('Cycle time:                  ' + '%.3f' % ct + ' s')
                        # print 'Elapsed time:        '+'%.3f' % tt +' s'
                        ptxt = repr(npts) + ' - ' + repr(count) + ' = ' + repr(
                            npts - count) + ' points ' + 'at ' + '%.3f' % at + ' s/pt                                 ' + 'ETA: ' + time.ctime(
                            time.time() + (npts - count) * at)
                    if (count == 1):
                        begin_time = time.time()
                        cycle_time = time.time()
                        self.progressbox.config(fg="white")
                        ptxt = "Mode: Scanning first point..."
                    self.progresstext.set(ptxt)
                    print('Program Counters:  DMOV' + repr(dmswitch))
                    print('-----------===========/////(' + repr(count) + ')/////=========[Taking Data]')
                    # check beamline condition or user pause request....
                    while (permit != 1):
                        self.statusbox.config(fg="pink")
                        self.progressbox.config(fg="pink")
                        self.progresstext.set("Paused: " + reason)
                        self.update()
                        time.sleep(0.5)
                        if (abort != 0): break

                    # take the data
                    print('Start Scanning')
                    self.take_data(xPV, tPV, yPV, inttime, trigPV, h5f)
                    print('Done Scanning')
                    print('================================ END')
                    ###End of data loop...
                    #
                    if (abort != 0): break
                    ###End of inner (X) loop...
                    #
                if (abort != 0): break
                ###End of middle (Theta) loop...
                #
            if (abort != 0): break
            ###End of outer (Y) loop...
            #
        if (ROI > cROI and abort == 0):
            self.pload(pfile, cROI)
            cROI += 1
            self.check_status()
        # If at the end of a multiple ROI scan, reset ROI:
        ROI = 1
        # Close the HDF file
        h5f.close()
        self.statusbox.config(fg="green")
        self.statustext.set("Scan Complete")
        self.progresstext.set('Done!')

    def move_motor_debug(self, zPV, zname, zpos, zmove, zq, zv, zvb, zta, ztrap):
        print('Motor movement started')
        t1 = time.time()
        zPV.move_absolute(zpos)
        while 1:
            position, status = zPV.get_extended_status()
            if (status & 0x1) == 0:
                break
            time.sleep(1.0)
        t2 = time.time()
        print(zname + '              Actual time:  ' + '%.3f' % (t2 - t1))
        print('Motor movement Ended')

    def take_data(self, xPV, tPV, yPV, inttime, trigPV, h5f, isContinuous=False, mcaData=None):
        # This routine must do the following four things:
        # 1) Start the Joerger counting
        # 2) Trigger the CCD
        # 3) Stop the Joerger
        # 4) Read out the Joerger channels of interest
        # 5) Throw all the data plus the motor positions into data matrix
        # covector that contains data from each point

        if (NoXRF == 0):
            a = mca_erasestart_pv.put(1)
            if (a == None):
                print('ERROR: Failed caput' + repr(mca_erasestart_pv.pvname))
                sys.exit(-1)
            if (mca_erasestart_pv.get() == 0):
                print('EraseStart = 0')

        thingy = 'Taking data at: '
        if (uy):
            my = yPV.position
            thingy = thingy + ' y = ' + '%.3f' % my
        if (ut):
            mt = tPV.position
            thingy = thingy + ' t = ' + '%.3f' % mt
        if (ux):
            mx = xPV.position
            thingy = thingy + ' x = ' + '%.3f' % mx
        self.statusbox.config(fg="gold")
        self.statustext.set(thingy)
        self.update()

        # Trigger the MAR
        a = mar_acq_pv.put(1)
        if (a == None):
            print('ERROR: Failed caput' + repr(trigPV.pvname))

        # Start the Joerger counting:
        a = j_start_pv.put(1)
        if (a == None):
            print('ERROR: Failed caput' + repr(j_start_pv.pvname))
            sys.exit(-1)

        # Open the shutter
        # a = sh_pv.put(0)
        # if (a == None):
        #      print 'ERROR: Failed caput' + `sh_pv.pvname`
        #      sys.exit(-1)

        # Wait for the specified time
        time.sleep(inttime)

        # Close the shutter
        # a = sh_pv.put(1)
        # if (a == None):
        #      print 'ERROR: Failed caput' + `sh_pv.pvname`
        #      sys.exit(-1)

        # Reset the trigger
        # a = trigPV.put(0)
        # if (a == None):
        #	print 'ERROR: Failed caput' + `trigPV.pvname`

        # if (newIntTime > 0):
        #  time.sleep(newIntTime)
        # Stop Joerger counting
        a = j_start_pv.put(0)
        if (a == None):
            print('ERROR: Failed caput' + repr(j_start_pv.pvname))
            sys.exit(-1)

        print(' Outside MCAv==0 line 1279')
        mcaData = McaData(nMCA)
        # Stop MCA counting
        if (NoXRF == 0):
            print(' Inside MCAv==0')
            a = mca_stop_pv.put(1, wait=1)
            if (a == None):
                print('ERROR: Failed caput' + repr(mca_stop_pv.pvname))
                sys.exit(-1)
            # give some extra time before reading the mca
            time.sleep(dxpfudge)

            # give some extra time before reading the mca
            dxpFudgeSleep = dxpfudge
            if (not (mcaData == None)):
                writeTime = self.writeToHDF(h5f, mcaData)
                dxpFudgeSleep = dxpFudgeSleep - writeTime

            if (dxpFudgeSleep > 0):
                time.sleep(dxpFudgeSleep)

            # We're done writing the file already
            # mcaData = McaData(nMCA)

            for i in range(nMCA):
                mcaData.live.append(mca_live_pv[i].get())
                mcaData.real.append(mca_real_pv[i].get())
                mcaData.dead.append(mca_dead_pv[i].get())

                #  Get data from MCA
                mcaData.mca.append(mca_data_pv[i].get())
            # Get ROIs
            tempb = []
            for j in range(nROI):
                tempb.append(mca_ROId_pv[i][j].get())
            mcaData.sROI.append(tempb)

        for i in range(len(scalerPV)):
            mcaData.jChannels.append(scalerPV[i].get() - inttime * dark[scaler[i] - 1])

        if (ux):
            mcaData.mx = mx
        if (ut):
            mcaData.mt = mt
        if (uy):
            mcaData.my = my
        mcaData.beamCurrent = xi_pv.get()

        endTime = time.time()
        # print "Time to read out MCA (s): ", (endTime-startTime)

        ##open file and append single data items to HDF file.

        if (not isContinuous):
            self.writeToHDF(h5f, mcaData)

        # print "Total data-taking time (s): ", (endTime-savedStartTime)
        # writestat("Detector Delay (s): " + str((endTime-savedStartTime-inttime)))

        # Wait for the CCD sequence to complete
        # print 'Waiting for CCD to complete (guessing '+`ccdfudge`+' s)...'
        # time.sleep(ccdfudge)
        print('Waiting for CCD to complete')
        while mar_acq_pv.get() != 0:
            time.sleep(0.1)
        mar_write_pv.put(1)
        return mcaData

    def writeToHDF(self, h5f, mcaData):
        startTime = time.time()

        dt1 = h5f.root.data.BL  # pX, pT, pY, BeamCurrent, Jchans
        et1 = dt1.row

        if (ux): et1['pX'] = mcaData.mx
        if (ut): et1['pT'] = mcaData.mt
        if (uy): et1['pY'] = mcaData.my
        et1['BeamCurrent'] = mcaData.beamCurrent
        et1['Jchans'] = mcaData.jChannels
        et1.append()
        dt1.flush()

        if (NoXRF == 0):  # include XRF
            for i in range(nMCA):
                MCAt = h5f.root.data._v_leaves['MCA1']  # LiveT, RealT, DeadT, sROI, data
                MCAe = MCAt.row

                MCAe['LiveT'] = mcaData.live[i]
                MCAe['RealT'] = mcaData.real[i]
                MCAe['DeadT'] = mcaData.dead[i]
                MCAe['sROI'] = np.array(mcaData.sROI[i])
                MCAe['data'] = mcaData.mca[i]
                MCAe.append()
                MCAt.flush()

        endTime = time.time()
        totalWriteTime = (endTime - startTime)
        # print "Time to write MCA to HDF file (s): ", totalWriteTime
        return totalWriteTime


class McaData:
    def __init__(self, n):
        self.live = []
        self.real = []
        self.dead = []
        self.mca = []
        self.jChannels = []
        self.sROI = []

        self.mx = 0
        self.mt = 0
        self.my = 0
        self.beamCurrent = 0


class MotorControl:
    def __init__(self, name, use_epic=False, mx_db=None):
        print('Init use_epic ' + str(use_epic))
        self.name = name
        self._use_epic = use_epic
        self._mx_db = mx_db
        self._init_motor()
        self._compute_speed_attr()

    def _compute_speed_attr(self):
        self.trap = (self.slew_speed + self.base_speed) * self.acceleration
        if self.slew_speed == self.base_speed or self.acceleration == 0.:
            self.mq = -1
        else:
            self.mq = (self.slew_speed - self.base_speed) / self.acceleration

    def _init_motor(self):
        print('Init ' + self.name)
        if self._use_epic:
            self.motor = Motor(self.name)
        else:
            self.motor = self._mx_db.get_record(self.name)

    def move(self, position):
        self._move_epic(position) if self._use_epic else self._move_mx(position)

    def _move_epic(self, position):
        print('Motor movement started using Epic')
        calc = self._log_move_time(position)
        t1 = time.time()
        self.motor.move(position)

        for tq in range(100):
            time.sleep(calc / 10.)
            done = self.motor.__getattr__('done_moving')
            if done != 0:
                break
        t2 = time.time()

        print('Motor movement Ended, Time: ' + '%.3f' % (t2 - t1))

    def _move_mx(self, position):
        print('Motor movement started using MX')
        calc = self._log_move_time(position)
        t1 = time.time()
        self.motor.move_absolute(position)
        while 1:
            position, status = self.motor.get_extended_status()
            if (status & 0x1) == 0:
                break
            time.sleep(1.0)
        t2 = time.time()
        print('Motor movement Ended, Time: ' + '%.3f' % (t2 - t1))

    def _log_move_time(self, position):
        move = abs(position - self.position)
        print('Motor diagnostics: (step = ' + '%.3f' % move + ')')
        calc = ''
        move_type = ''
        if self.mq < 0:
            calc = move / self.slew_speed
            move_type = 'Top-hat'
        elif move >= self.trap:
            calc = (move + (self.slew_speed - self.base_speed) * self.acceleration) / self.slew_speed
            move_type = 'Trapezoidal'
        elif move < self.trap:
            calc = 2 * (np.sqrt(self.base_speed ** 2 + self.mq * move) - self.base_speed) / self.mq
            move_type = 'Triangular'
        print('Calculated time:  ' + '%.3f' % calc + ' s (' + move_type + ')')
        return calc

    @property
    def slew_speed(self):
        return self.motor.__getattr__('slew_speed') if self._use_epic else self.motor.get_speed()

    @property
    def base_speed(self):
        return self.motor.__getattr__('base_speed') if self._use_epic else self.motor.get_base_speed()

    @property
    def acceleration(self):
        return self.motor.__getattr__('acceleration') if self._use_epic else \
            self.motor.get_raw_acceleration_parameters()[0]

    @property
    def description(self):
        return self.motor.description if self._use_epic else 'Connected'

    @property
    def position(self):
        return self.motor.get_position(readback=1) if self._use_epic else self.motor.get_position()


if __name__ == '__main__':
    try:
        # First try to get the name from an environment variable.
        database_filename = os.environ["MXDATABASE"]
    except:
        # If the environment variable does not exist, construct
        # the filename for the default MX database.
        mxdir = get_mxdir()
        database_filename = os.path.join(mxdir, "etc", "mxmotor.dat")
        database_filename = os.path.normpath(database_filename)
    try:
        mx_database = mp.setup_database(database_filename)
        mx_database.set_plot_enable(2)
        mx_database.set_program_name("udiff")
        mx_database.set_program_name("udiff")
    except:
        print('MX is not supported')

    # Run the app
    mw = MainWindow(None)


    def writestat(message, color='gold', object=mw):
        object.statusbox.config(fg=color)
        object.statustext.set(message)
        object.update()


    mw.pack()
    mw.mainloop()
