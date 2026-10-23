/* Input definitions for each engine type.
 * A field maps a GUI input onto a path of the ProJet config dictionary. */

const F = (path, label, sym, unit, opts = {}) => ({ path, label, sym, unit, step: 'any', ...opts });

const EFF = { min: 0, max: 1, step: 0.005 };

const GROUPS = {
  flight: {
    title: 'Flight conditions', color: '#0ea5e9',
    fields: [
      F(['flightConditions', 'altitude_km'], 'Altitude', 'z', 'km', { step: 0.5, isa: true, sweep: false, help: 'Used for the exam text; press ISA to fill T, p, ρ' }),
      F(['airProperties', 'temperature'], 'Static temperature', 'T₀', 'K', { step: 1, min: 1 }),
      F(['airProperties', 'pressure'], 'Static pressure', 'p₀', 'Pa', { step: 100, min: 1 }),
      F(['airProperties', 'density'], 'Density', 'ρ₀', 'kg/m³', { step: 0.01, min: 0 }),
      F(['components', 'intake', 'mach'], 'Flight Mach', 'M₀', '–', { step: 0.01, min: 0 }),
      F(['components', 'intake', 'Phi'], 'Intake diameter', 'D', 'm', { step: 0.05, min: 0 }),
    ],
  },
  intake: {
    title: 'Intake', color: '#38bdf8',
    fields: [F(['components', 'intake', 'efficiency'], 'Pressure recovery', 'πd', '–', { ...EFF, def: 1.0 })],
  },
  propeller: {
    title: 'Propeller & gearbox', color: '#a78bfa',
    fields: [
      F(['components', 'propeller', 'Phi'], 'Propeller diameter', 'Dp', 'm', { step: 0.1, min: 0 }),
      F(['components', 'propeller', 'efficiency'], 'Propeller efficiency', 'ηp', '–', { ...EFF, def: 1.0 }),
      F(['components', 'propeller', 'gearbox_efficiency'], 'Gearbox efficiency', 'ηgb', '–', { ...EFF, def: 1.0 }),
      F(['components', 'propeller', 'alpha_power'], 'Power split to propeller', 'α', '–',
        { ...EFF, optional: { label: 'Use optimal α', value: 0.85 } }),
    ],
  },
  fan: {
    title: 'Fan', color: '#60a5fa',
    fields: [
      F(['components', 'fan', 'pressure_ratio'], 'Pressure ratio', 'βf', '–', { step: 0.05, min: 1 }),
      F(['components', 'fan', 'efficiency'], 'Adiabatic efficiency', 'ηf', '–', { ...EFF, def: 1.0 }),
      F(['components', 'fan', 'mechanical_efficiency'], 'Mechanical efficiency', 'ηm,f', '–', { ...EFF, def: 1.0 }),
    ],
  },
  fanBPR: {
    title: 'Fan', color: '#60a5fa',
    fields: [
      F(['components', 'fan', 'BPR'], 'Bypass ratio', 'BPR', '–', { step: 0.5, min: 0 }),
      F(['components', 'fan', 'pressure_ratio'], 'Pressure ratio', 'βf', '–', { step: 0.05, min: 1 }),
      F(['components', 'fan', 'efficiency'], 'Adiabatic efficiency', 'ηf', '–', { ...EFF, def: 1.0 }),
      F(['components', 'fan', 'mechanical_efficiency'], 'Mechanical efficiency', 'ηm,f', '–', { ...EFF, def: 1.0 }),
    ],
  },
  compressor: {
    title: 'Compressor', color: '#3b82f6',
    fields: [
      F(['components', 'compressor', 'pressure_ratio'], 'Pressure ratio', 'βc', '–', { step: 0.5, min: 1 }),
      F(['components', 'compressor', 'efficiency'], 'Adiabatic efficiency', 'ηc', '–', { ...EFF, def: 1.0 }),
      F(['components', 'compressor', 'mechanical_efficiency'], 'Mechanical efficiency', 'ηm,c', '–', { ...EFF, def: 1.0 }),
    ],
  },
  combustor: {
    title: 'Combustor', color: '#ef4444',
    modes: {
      label: 'Specify',
      options: [
        { label: 'Turbine inlet T', field: F(['components', 'combustor', 'outlet_temperature'], 'Turbine inlet temperature', 'T₄⁰', 'K', { step: 10, min: 1, value: 1450 }) },
        { label: 'Fuel/air ratio', field: F(['components', 'combustor', 'fuel_ratio'], 'Fuel/air ratio', 'f', '–', { step: 0.001, min: 0, value: 0.02 }) },
      ],
    },
    fields: [
      F(['components', 'combustor', 'efficiency'], 'Combustion efficiency', 'ηb', '–', { ...EFF, def: 1.0 }),
      F(['components', 'combustor', 'mechanical_efficiency'], 'Pressure recovery', 'πb', '–', { ...EFF, def: 1.0 }),
    ],
  },
  turbine: {
    title: 'Turbine', color: '#f97316',
    fields: [
      F(['components', 'turbine', 'efficiency'], 'Adiabatic efficiency', 'ηt', '–', { ...EFF, def: 1.0 }),
      F(['components', 'turbine', 'mechanical_efficiency'], 'Mechanical efficiency', 'ηm,t', '–', { ...EFF, def: 1.0 }),
    ],
  },
  turbineHigh: {
    title: 'High-pressure turbine', color: '#f97316',
    fields: [
      F(['components', 'turbineHigh', 'efficiency'], 'Adiabatic efficiency', 'ηHPT', '–', { ...EFF, def: 1.0 }),
      F(['components', 'turbineHigh', 'mechanical_efficiency'], 'Mechanical efficiency', 'ηm,HPT', '–', { ...EFF, def: 1.0 }),
    ],
  },
  turbineLow: {
    title: 'Low-pressure turbine', color: '#fb923c',
    fields: [
      F(['components', 'turbineLow', 'efficiency'], 'Adiabatic efficiency', 'ηLPT', '–', { ...EFF, def: 1.0 }),
      F(['components', 'turbineLow', 'mechanical_efficiency'], 'Mechanical efficiency', 'ηm,LPT', '–', { ...EFF, def: 1.0 }),
    ],
  },
  afterburner: {
    title: 'Afterburner', color: '#dc2626',
    toggle: {
      label: 'Afterburner on',
      paths: [['components', 'postCombustor'], ['postcombustionProperties']],
      values: [
        { fuel_ratio: 0.03, efficiency: 0.98, mechanical_efficiency: 0.95 },
        { gamma: 1.3, cp: 1243, R: 286.6 },
      ],
    },
    modes: {
      label: 'Specify',
      options: [
        { label: 'Fuel/air ratio', field: F(['components', 'postCombustor', 'fuel_ratio'], 'Fuel/air ratio', 'fAB', '–', { step: 0.001, min: 0, value: 0.03 }) },
        { label: 'Outlet T', field: F(['components', 'postCombustor', 'outlet_temperature'], 'Outlet temperature', 'TAB⁰', 'K', { step: 10, min: 1, value: 2000 }) },
      ],
    },
    fields: [
      F(['components', 'postCombustor', 'efficiency'], 'Combustion efficiency', 'ηAB', '–', { ...EFF, def: 1.0 }),
      F(['components', 'postCombustor', 'mechanical_efficiency'], 'Pressure recovery', 'πAB', '–', { ...EFF, def: 1.0 }),
      { subhead: 'Afterburner gas' },
      F(['postcombustionProperties', 'cp'], 'Specific heat', 'cp,AB', 'J/kgK', { step: 1, def: 1155 }),
      F(['postcombustionProperties', 'gamma'], 'Heat capacity ratio', 'γAB', '–', { step: 0.01, def: 1.33 }),
      F(['postcombustionProperties', 'R'], 'Gas constant', 'RAB', 'J/kgK', { step: 0.1, def: 286.58 }),
    ],
  },
  nozzle: {
    title: 'Nozzle', color: '#94a3b8',
    fields: [
      F(['components', 'nozzle', 'efficiency'], 'Adiabatic efficiency', 'ηn', '–', { ...EFF, def: 1.0 }),
      { check: ['components', 'nozzle', 'onlyConvergent'], label: 'Convergent-only nozzle (choked, M = 1)' },
    ],
  },
  nozzlesSF: {
    title: 'Nozzles', color: '#94a3b8',
    fields: [
      F(['components', 'nozzleMain', 'efficiency'], 'Core nozzle efficiency', 'ηn,H', '–', { ...EFF, def: 1.0 }),
      F(['components', 'nozzleSecondary', 'efficiency'], 'Bypass nozzle efficiency', 'ηn,C', '–', { ...EFF, def: 1.0 }),
    ],
  },
  gases: {
    title: 'Gas & fuel properties', color: '#64748b', closed: true,
    fields: [
      { subhead: 'Air' },
      F(['airProperties', 'cp'], 'Specific heat', 'cp,a', 'J/kgK', { step: 1, def: 1004 }),
      F(['airProperties', 'gamma'], 'Heat capacity ratio', 'γa', '–', { step: 0.01, def: 1.4 }),
      F(['airProperties', 'R'], 'Gas constant', 'Ra', 'J/kgK', { step: 0.1, def: 287 }),
      { subhead: 'Combustion gas' },
      F(['hotGasProperties', 'cp'], 'Specific heat', 'cp,g', 'J/kgK', { step: 1, def: 1155 }),
      F(['hotGasProperties', 'gamma'], 'Heat capacity ratio', 'γg', '–', { step: 0.01, def: 1.33 }),
      F(['hotGasProperties', 'R'], 'Gas constant', 'Rg', 'J/kgK', { step: 0.1, def: 286.58 }),
      { subhead: 'Fuel' },
      F(['fuelProperties', 'calorific'], 'Lower heating value', 'LHV', 'MJ/kg', { step: 0.5, scale: 1e6, def: 42e6 }),
    ],
  },
};

const ENGINES = {
  turbojet: {
    label: 'Turbojet',
    groups: ['flight', 'intake', 'compressor', 'combustor', 'turbine', 'afterburner', 'nozzle', 'gases'],
  },
  turbofan_SF: {
    label: 'Turbofan · separate',
    groups: ['flight', 'intake', 'fanBPR', 'compressor', 'combustor', 'turbineHigh', 'turbineLow', 'nozzlesSF', 'gases'],
  },
  turbofan_AF: {
    label: 'Turbofan · mixed',
    groups: ['flight', 'intake', 'fan', 'compressor', 'combustor', 'turbineHigh', 'turbineLow', 'afterburner', 'nozzle', 'gases'],
  },
  turboprop: {
    label: 'Turboprop',
    groups: ['flight', 'propeller', 'intake', 'compressor', 'combustor', 'turbineHigh', 'turbineLow', 'nozzle', 'gases'],
  },
};

const ENGINE_ICONS = {
  turbojet: '<svg viewBox="0 0 60 30"><path d="M2 9h8l6-3h22l8 4 12 2v6l-12 2-8 4H16l-6-3H2z" fill="currentColor" opacity=".85"/></svg>',
  turbofan_SF: '<svg viewBox="0 0 60 30"><path d="M2 3h40l8 6v12l-8 6H2z" fill="currentColor" opacity=".35"/><path d="M8 10h34l8 3 8 1v2l-8 1-8 3H8z" fill="currentColor"/></svg>',
  turbofan_AF: '<svg viewBox="0 0 60 30"><path d="M2 3h44l12 8v8l-12 8H2z" fill="currentColor" opacity=".35"/><path d="M8 10h30l8 3v4l-8 3H8z" fill="currentColor"/></svg>',
  turboprop: '<svg viewBox="0 0 60 30"><rect x="4" y="1" width="3" height="28" rx="1.5" fill="currentColor"/><path d="M8 11h10l6-2h20l10 4v4l-10 4H24l-6-2H8z" fill="currentColor" opacity=".85"/></svg>',
};
