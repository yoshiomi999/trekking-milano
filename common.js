function formatDate(dataIso, fallback){
  if (!dataIso) return fallback;

  const [year, month, day] = dataIso.split('-').map(Number);
  const mesi = [
    'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
    'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'
  ];

  return `${day} ${mesi[month - 1]} ${year}`;
}

function formatWeekday(dataIso, fallback){
  if (dataIso) {
    const [year, month, day] = dataIso.split('-').map(Number);
    const date = new Date(year, month - 1, day);
    return ['Domenica', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato'][date.getDay()];
  }

  const abbreviations = {
    Lun: 'Lunedì',
    Mar: 'Martedì',
    Mer: 'Mercoledì',
    Gio: 'Giovedì',
    Ven: 'Venerdì',
    Sab: 'Sabato',
    Dom: 'Domenica'
  };
  return abbreviations[fallback?.split(' ')[0]] || '';
}

function dayClass(dataIso, fallback){
  if (dataIso) {
    const [year, month, day] = dataIso.split('-').map(Number);
    const weekday = new Date(year, month - 1, day).getDay();
    if (weekday === 6) return 'sat';
    if (weekday === 0) return 'dom';
  }

  if (fallback?.startsWith('Sab')) return 'sat';
  if (fallback?.startsWith('Dom')) return 'dom';
  return '';
}
