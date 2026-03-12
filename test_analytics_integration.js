/* Test file to verify analytics dashboard integration */
console.log('=== ANALYTICS DASHBOARD INTEGRATION TEST ===');

// Test 1: Check if AnalyticsDashboard class exists
if (typeof AnalyticsDashboard !== 'undefined') {
    console.log('✅ AnalyticsDashboard class loaded');
} else {
    console.error('❌ AnalyticsDashboard class not found');
}

// Test 2: Check if analytics page exists in DOM
const analyticsPage = document.getElementById('page-analytics');
if (analyticsPage) {
    console.log('✅ Analytics page container found');
} else {
    console.error('❌ Analytics page container not found');
}

// Test 3: Check if analytics nav item exists
const analyticsNav = document.querySelector('[data-page="analytics"]');
if (analyticsNav) {
    console.log('✅ Analytics navigation item found');
    console.log(`   Visibility: ${window.getComputedStyle(analyticsNav).display}`);
} else {
    console.error('❌ Analytics navigation item not found');  
}

// Test 4: Check if App.pages.analytics is properly configured
if (App && App.pages && App.pages.analytics) {
    console.log('✅ Analytics page config found');
    console.log(`   Title: ${App.pages.analytics.title}`);
    console.log(`   Component: ${typeof App.pages.analytics.component}`);
} else {
    console.error('❌ Analytics page config not found');
}

// Test 5: Check Chart.js availability (required for dashboard)
if (typeof Chart !== 'undefined') {
    console.log('✅ Chart.js library available');
} else {
    console.error('❌ Chart.js library not found');
}

console.log('=== TEST COMPLETE ===');