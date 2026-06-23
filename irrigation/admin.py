from django.contrib import admin

from .models import (
    BassinageEvent,
    DtiScore,
    FrostEvent,
    InvisibleLossDetection,
    IrrigationProgram,
    IrrigationSession,
    IrrigationZone,
    NdviData,
    PumpingStation,
    WaterMeter,
    WaterQuota,
    EnergyLog,
)

admin.site.register(
    [
        IrrigationZone,
        IrrigationProgram,
        IrrigationSession,
        PumpingStation,
        BassinageEvent,
        WaterMeter,
        EnergyLog,
        WaterQuota,
        DtiScore,
        FrostEvent,
        NdviData,
        InvisibleLossDetection,
    ]
)
