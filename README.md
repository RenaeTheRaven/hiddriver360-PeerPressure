# hiddriver360-PeerPressure
Rework of the hiddriver360 plugin to work on PressurePoint modded Xbox 360s


This is an AI-driven rework of the plugin that let's you use any controller on an Xbox 360.


Let me be clear- this may be AI-made, but I'm not an idiot. I'm a Unix system administrator of 12 years.


I may not be a strictly software development oriented tech, but I know a thing or two, so there was plenty of hand-holding.



The old version needed to be used with DashLauncher as a plugin because of how it used system calls.
Some of how PeerPressure patches the kernel was RE'd, in conjunction with a chain-load to Aurora. 
This took a combination of a questionably sourced SDK, and some really oddball testing.

The result? A 4KB patch to the kernel, and a custom .xex that loads with Aurora and lets you use anything from a DDR dance mat for the Gamecube to a DS5.


This was really fun to get working. 
