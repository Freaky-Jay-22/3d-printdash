"""Bambu codes that are only an instruction, a question or a status - not an error.

Generated from Bambu's own message texts (the HMS / error lists also used by Bambu Studio):
a code is listed only if its text is an instruction / status for every printer model and
contains nothing that points to a fault (failed, error, abnormal, clogged, broken ...).
Everything not listed here is reported. Grouped by what the message is about."""

# HMS codes (AAAA_BBBB_CCCC_DDDD)
HMS_HINTS = frozenset({
    # automatic adjustments the printer reports (fan, filter, chamber light, cooling advice)
    "0300_0100_0003_000F", "0300_9400_0003_0001", "0300_9E00_0003_0001", "0300_A700_0003_0001",
    "0300_AD00_0003_0001", "0C00_0400_0003_0026",
    # status while waiting (first layer inspection, dry cooling, air purification, bed leveling)
    "0300_1800_0003_0009", "0300_2D00_0003_0009", "0500_0400_0003_0057", "0700_5600_0003_0001",
    "0701_5600_0003_0001", "0702_5600_0003_0001", "0703_5600_0003_0001", "0704_5600_0003_0001",
    "0705_5600_0003_0001", "0706_5600_0003_0001", "0707_5600_0003_0001", "0C00_0300_0003_000B",
    "12FF_2000_0003_0007", "1800_5600_0003_0001", "1801_5600_0003_0001", "1802_5600_0003_0001",
    "1803_5600_0003_0001", "1804_5600_0003_0001", "1805_5600_0003_0001", "1806_5600_0003_0001",
    "1807_5600_0003_0001", "2A00_5600_0003_0001",
    # calibration still to do (setup after a change)
    "0300_2E00_0003_0001", "0300_2F00_0002_0002", "0800_1A00_0001_0008", "0C00_0200_0001_0005",
    "1A00_5000_0002_0001",
    # pause by the user or door open (the pause notification covers it)
    "0300_9600_0001_0001", "1A00_0100_0001_006B",
    # laser / cutting module setup steps (place mat or platform, plug in, calibrate)
    "0300_DB00_0002_0001", "0500_0400_0002_0031", "0500_0400_0002_0032", "0500_0400_0002_0033",
    "0500_0400_0002_0035", "0500_0400_0002_0037", "0500_0400_0002_0038", "0500_0400_0002_0039",
    "0C00_0400_0002_0002", "0C00_0400_0002_0003", "0C00_0400_0002_0029", "0C00_0400_0002_0032",
    "0C00_0400_0003_0024",
    # maintenance reminders (3D-PrintDash has its own)
    "0501_0400_0003_0004", "0501_0400_0003_0005", "0501_0400_0003_0007",
    # AMS drying: answers and power hints
    "0700_2500_0002_0001", "0701_2500_0002_0001", "0702_2500_0002_0001", "0703_2500_0002_0001",
    "0704_2500_0002_0001", "0705_2500_0002_0001", "0706_2500_0002_0001", "0707_2500_0002_0001",
    "1800_2500_0002_0001", "1801_2500_0002_0001", "1802_2500_0002_0001", "1803_2500_0002_0001",
    "1804_2500_0002_0001", "1805_2500_0002_0001", "1806_2500_0002_0001", "1807_2500_0002_0001",
    # AMS switched off: load from the spool holder
    "0700_5100_0003_0001", "1200_5100_0003_0001", "1800_5100_0003_0001",
    # loading / unloading steps (feed, observe nozzle, pull out, insert filament)
    "07F7_2000_0002_0002", "07F7_2000_0002_0004", "07F8_2000_0002_0002", "07F8_2000_0002_0004",
    "07F9_2000_0002_0002", "07F9_2000_0002_0004", "07FA_2000_0002_0002", "07FA_2000_0002_0004",
    "07FB_2000_0002_0002", "07FB_2000_0002_0004", "07FC_2000_0002_0002", "07FC_2000_0002_0004",
    "07FD_2000_0002_0002", "07FD_2000_0002_0004", "07FE_2000_0002_0002", "07FE_2000_0002_0004",
    "07FF_2000_0002_0002", "07FF_2000_0002_0004", "12FF_2000_0002_0004", "18FE_2000_0002_0002",
    "18FE_2000_0002_0004", "18FE_7000_0002_0003", "18FF_2000_0002_0002", "18FF_2000_0002_0004",
    "18FF_7000_0002_0003",
})

# print_error codes (8 hex digits)
ERROR_HINTS = frozenset({
    # pause by the user or door open (the pause notification covers it)
    0x03008001, 0x0300800F,
    # calibration still to do (setup after a change)
    0x03008030,
    # answers to an action at the printer (busy, upgrading, already bound, heat nozzle first)
    0x0300804F, 0x0300C012, 0x05004019, 0x05004030, 0x05004032, 0x05004045,
    0x05004066, 0x0500804E, 0x05014019, 0x05024002,
    # laser / cutting module setup steps (place mat or platform, plug in, calibrate)
    0x03008053, 0x03008054, 0x05004065, 0x05004075, 0x05004076, 0x05008055,
    0x05008056, 0x05008058, 0x05008059, 0x0500805A, 0x0500805B, 0x0500805C,
    0x05008063, 0x05008064, 0x05008066, 0x05008067, 0x05008068, 0x0500806C,
    0x0500806F, 0x05008071, 0x05008074, 0x05008079, 0x0500807B, 0x0500807C,
    0x0500807D, 0x0500807E, 0x05008082, 0x05008083, 0x05008090, 0x050080C6,
    0x050080C8, 0x050080CA, 0x050080D8, 0x0C008057,
    # AMS drying: answers and power hints
    0x05004040, 0x0500C032, 0x0500C045, 0x0500C04E, 0x0502C010, 0x07008017,
    0x07018017, 0x07028017, 0x07038017, 0x18008017, 0x18018017, 0x18028017,
    0x18038017,
    # loading / unloading steps (feed, observe nozzle, pull out, insert filament)
    0x07F6C011, 0x07F6C012, 0x07F7C006, 0x07F7C010, 0x07F7C011, 0x07F7C012,
    0x07F8C006, 0x07F8C010, 0x07F8C011, 0x07F8C012, 0x07F9C006, 0x07F9C010,
    0x07F9C011, 0x07F9C012, 0x07FAC006, 0x07FAC010, 0x07FAC011, 0x07FAC012,
    0x07FBC006, 0x07FBC010, 0x07FBC011, 0x07FBC012, 0x07FCC006, 0x07FCC010,
    0x07FCC011, 0x07FCC012, 0x07FDC006, 0x07FDC010, 0x07FDC011, 0x07FDC012,
    0x07FEC006, 0x07FEC009, 0x07FEC00A, 0x07FEC010, 0x07FEC011, 0x07FEC012,
    0x07FFC006, 0x07FFC009, 0x07FFC00A, 0x07FFC010, 0x07FFC016, 0x12FF8006,
    0x12FFC006, 0x18FE8006, 0x18FE8007, 0x18FEC006, 0x18FEC009, 0x18FEC00A,
    0x18FF8006, 0x18FF8007, 0x18FFC006, 0x18FFC009, 0x18FFC00A,
    # timelapse mode question
    0x1000C003,
})
