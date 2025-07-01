// i18n.js - Handles translations and language switching for the Stock Filter app

const translations = {
    en: {
        title: 'Stock Filter',
        search_criteria: 'Search Criteria',
        collapse: 'Collapse',
        expand: 'Expand',
        revenue_required: 'Revenue (Required)',
        min_revenue: 'Minimum Revenue',
        max_revenue: 'Maximum (Optional)',
        return_on_equity: 'Return on Equity %',
        min_roe: 'Minimum ROE %',
        revenue_growth: 'Revenue Growth %',
        period_years: 'Period (Years)',
        min_growth: 'Minimum Growth %',
        years: 'Number of Years',
        earnings_growth: 'Earnings Growth %',
        search: 'Search',
        searching: 'Searching...',
        tip_multi_sort: "Tip: Hold <kbd class='px-1 py-0.5 bg-gray-200 rounded border text-xs'>Shift</kbd> to sort by more than one column.",
        reset_sort: 'Reset sorting',
        export_csv: 'Export CSV',
        symbol: 'symbol',
        symbols: 'symbols',
        found: 'found',
        min_revenue_required: 'Minimum revenue is required',
        no_results: 'No results found',
        error: 'Error',
        error_searching: 'Error searching',
        error_exporting: 'Error exporting',
        no_data_export: 'No data to export',
        language: 'Language:',
    },
    de: {
        title: 'Aktienfilter',
        search_criteria: 'Suchkriterien',
        collapse: 'Einklappen',
        expand: 'Ausklappen',
        revenue_required: 'Umsatz (erforderlich)',
        min_revenue: 'Mindestumsatz',
        max_revenue: 'Maximal (optional)',
        return_on_equity: 'Eigenkapitalrendite %',
        min_roe: 'Mindest-EKR %',
        revenue_growth: 'Umsatzwachstum %',
        period_years: 'Zeitraum (Jahre)',
        min_growth: 'Mindestwachstum %',
        years: 'Anzahl Jahre',
        earnings_growth: 'Gewinnwachstum %',
        search: 'Suchen',
        searching: 'Suche...',
        tip_multi_sort: "Tipp: Halten Sie <kbd class='px-1 py-0.5 bg-gray-200 rounded border text-xs'>Shift</kbd> gedrückt, um nach mehreren Spalten zu sortieren.",
        reset_sort: 'Sortierung zurücksetzen',
        export_csv: 'CSV exportieren',
        symbol: 'Symbol',
        symbols: 'Symbole',
        found: 'gefunden',
        min_revenue_required: 'Mindestumsatz ist erforderlich',
        no_results: 'Keine Ergebnisse gefunden',
        error: 'Fehler',
        error_searching: 'Fehler bei der Suche',
        error_exporting: 'Fehler beim Exportieren',
        no_data_export: 'Keine Daten zum Exportieren',
        language: 'Sprache:',
    }
};

let currentLang = localStorage.getItem('lang');
if (!currentLang) {
    const sysLang = navigator.language || navigator.userLanguage || 'en';
    if (sysLang.startsWith('de')) {
        currentLang = 'de';
    } else {
        currentLang = 'en';
    }
    localStorage.setItem('lang', currentLang);
}

function t(key) {
    return translations[currentLang][key] || key;
}

function updateI18n() {
    document.getElementById('title').textContent = t('title');
    if (document.getElementById('langLabel')) document.getElementById('langLabel').textContent = t('language');
    document.getElementById('collapseCriteriaBtnText').textContent = window.isCollapsed ? t('expand') : t('collapse');
    document.getElementById('searchCriteriaTitle').textContent = t('search_criteria');
    document.getElementById('revenueLabel').textContent = t('revenue_required');
    document.getElementById('revenueMin').placeholder = t('min_revenue');
    document.getElementById('revenueMax').placeholder = t('max_revenue');
    document.getElementById('roeLabel').textContent = t('return_on_equity');
    document.getElementById('roeMin').placeholder = t('min_roe');
    document.getElementById('revenueGrowthLabel').textContent = t('revenue_growth');
    document.getElementById('revenueGrowthMin').placeholder = t('min_growth');
    document.getElementById('revenueGrowthYearsLabel').textContent = t('period_years');
    document.getElementById('revenueGrowthYears').placeholder = t('years');
    document.getElementById('earningsGrowthLabel').textContent = t('earnings_growth');
    document.getElementById('earningsGrowthMin').placeholder = t('min_growth');
    document.getElementById('earningsGrowthYearsLabel').textContent = t('period_years');
    document.getElementById('earningsGrowthYears').placeholder = t('years');
    document.getElementById('searchButtonText').textContent = t('search');
    document.getElementById('exportBtn').textContent = t('export_csv');
    document.getElementById('multiSortTip').innerHTML = t('tip_multi_sort');
    document.getElementById('resetSortBtn').textContent = t('reset_sort');
    // Update result count if present
    if (window.currentResults && window.currentResults.length) {
        if (typeof updateResultCount === 'function') updateResultCount(window.currentResults.length);
        if (typeof renderTable === 'function') renderTable(window.currentResults, window.lastHeaders);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const langSelect = document.getElementById('langSelect');
    if (langSelect) {
        langSelect.value = currentLang;
        langSelect.addEventListener('change', (e) => {
            currentLang = e.target.value;
            localStorage.setItem('lang', currentLang);
            updateI18n();
            if (window.currentResults && window.currentResults.length && typeof updateResultCount === 'function') {
                updateResultCount(window.currentResults.length);
            }
        });
    }
    updateI18n();
});

window.t = t;
window.updateI18n = updateI18n;
window.currentLang = currentLang;
