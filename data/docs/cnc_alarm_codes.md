# CNC Alarm Codes and First Actions

Applies to the MetalWorks controls on CNC-01, CNC-02 and CNC-03. The alarm number appears on the control screen. Do the first action yourself; if the alarm comes back, stop the machine and call maintenance. Never reset an alarm more than twice without finding the cause.

## Spindle alarms
- AL-1010 Spindle overload: the cut is too heavy. Reduce feed by 20 percent, check the tool for wear, restart the cycle.
- AL-1020 Spindle vibration: follow the spindle vibration procedure in the CNC milling maintenance document (feed hold, retract, check tool holder seating and balance).
- AL-1030 Spindle overheating: stop the spindle and let it cool for 15 minutes. Check the spindle chiller level. Two overheating alarms in one shift = maintenance request.
- AL-1040 Drawbar clamp failure: do not run the spindle. Tag the machine out and call maintenance; the tool may be released at speed.

## Axis alarms
- AL-2010 Axis overtravel: the axis hit a soft limit. Jog the axis back in manual mode, check the work offset and the program for a wrong coordinate.
- AL-2020 Following error: the axis could not follow the command. Check for a crash or a jammed chip in the way covers. After a crash, do not restart before maintenance has checked the alignment.
- AL-2030 Axis drive fault: power the machine down for 2 minutes, then restart once. If it returns, call maintenance.

## Tool changer alarms
- AL-3010 Tool not clamped in magazine: check the pocket for chips and the tool holder for damage.
- AL-3020 Tool change timeout: the changer did not complete. Put the machine in manual, follow the tool-changer recovery steps on the machine door. Never put a hand in the changer without lockout-tagout.

## Coolant and air alarms
- AL-4010 Coolant level low: top up with cutting fluid mixed at 6 to 8 percent (CUT-FLUID-20L).
- AL-4020 Coolant pressure low: clean the coolant tank filter, then check the pump.
- AL-4030 Air pressure low: the air supply must read 5.5 to 6.5 bar at the filter regulator. Check the AF3 air filter element (AIR-FILTER-AF3) and replace it if clogged.

## Door and safety alarms
- AL-5010 Door open during cycle: close the door; the interlock stopped the cycle. Never bypass the door interlock.
- AL-5020 Emergency stop pressed: find out why before releasing it. Only the shift supervisor restarts the machine after an emergency stop.
