// https://apexcharts.com/javascript-chart-demos/line-charts/zoomable-timeseries/
var isDarkTheme = document.documentElement.getAttribute('data-theme') === 'dark';
var options = {
    series: [],
    chart: {
        type: 'area',
        stacked: false,
        height: 520,
        zoom: {
            type: 'x',
            enabled: true,
            autoScaleYaxis: true
        },
        // background: '#2B2D3E',
        foreColor: isDarkTheme ? '#e5e7eb' : '#374151',
        toolbar: {
            autoSelected: 'zoom'
        },
        animations: {
            enabled: false
        }
    },
    dataLabels: {
        enabled: false
    },
    stroke: {
        curve: 'smooth',
    },
    markers: {
        size: 0,
    },
    title: {
        text: 'Channel points (dates are displayed in UTC)',
        align: 'left'
    },
    colors: [isDarkTheme ? "#a78bfa" : "#6d28d9"],
    fill: {
        type: 'gradient',
        gradient: {
            shadeIntensity: 1,
            inverseColors: false,
            opacityFrom: 0.5,
            opacityTo: 0,
            stops: [0, 90, 100]
        },
    },
    yaxis: {
        title: {
            text: 'Channel points'
        },
    },
    xaxis: {
        type: 'datetime',
        labels: {
            datetimeUTC: false
        }
    },
    tooltip: {
        theme: isDarkTheme ? 'dark' : 'light',
        shared: false,
        x: {
            show: true,
            format: 'HH:mm:ss dd MMM',
        },
        custom: ({
            series,
            seriesIndex,
            dataPointIndex,
            w
        }) => {
            return (`<div class="apexcharts-active">
                <div class="apexcharts-tooltip-title">${w.globals.seriesNames[seriesIndex]}</div>
                <div class="apexcharts-tooltip-series-group apexcharts-active" style="order: 1; display: flex; padding-bottom: 0px !important;">
                    <div class="apexcharts-tooltip-text">
                        <div class="apexcharts-tooltip-y-group">
                            <span class="apexcharts-tooltip-text-label"><b>Points</b>: ${series[seriesIndex][dataPointIndex]}</span><br>
                            <span class="apexcharts-tooltip-text-label"><b>Reason</b>: ${w.globals.seriesZ[seriesIndex][dataPointIndex] ? w.globals.seriesZ[seriesIndex][dataPointIndex] : ''}</span>
                        </div>
                    </div>
                </div>
                </div>`)
        }
    },
    noData: {
        text: 'Loading...'
    }
};

var chart = new ApexCharts(document.querySelector("#chart"), options);
var currentStreamer = null;
var annotations = [];

var streamersList = [];
var sortBy = "Name ascending";
var sortField = 'name';

var startDate = new Date();
startDate.setDate(startDate.getDate() - daysAgo);
var endDate = new Date();

$(document).ready(function () {
    // Variable to keep track of whether log checkbox is checked
    var isLogCheckboxChecked = $('#log').prop('checked');

    // Variable to keep track of whether auto-update log is active
    var autoUpdateLog = true;

    // Variable to keep track of the last received log index
    var lastReceivedLogIndex = -1;

    $('#auto-update-log').click(() => {
        autoUpdateLog = !autoUpdateLog;
        $('#auto-update-log').text(autoUpdateLog ? '⏸️' : '▶️');

        if (autoUpdateLog) {
            getLog();
        }
    });

    // Poll the log endpoint. The server numbers its lines and tells us the last number we got.
    var logTimer = null;
    function getLog() {
        clearTimeout(logTimer);
        if (!isLogCheckboxChecked) return;
        $.ajax({
            url: '/log',
            data: { since: lastReceivedLogIndex },
            dataType: 'text',
            cache: false
        }).done(function (data, status, xhr) {
            var box = $("#log-content")[0];
            var wasFirst = lastReceivedLogIndex === -1;
            // First load, or the miner restarted: start from a clean panel
            if (lastReceivedLogIndex === -1 || xhr.getResponseHeader('X-Log-Reset') === '1') {
                $("#log-content").text('');
            }
            var seq = parseInt(xhr.getResponseHeader('X-Log-Seq'));
            if (!isNaN(seq)) lastReceivedLogIndex = seq;
            if (data) {
                var atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
                $("#log-content").append(document.createTextNode(data));
                // Keep the panel from growing without limit
                var text = box.textContent;
                if (text.length > 400000) box.textContent = text.slice(text.length - 300000);
                if (atBottom || wasFirst) box.scrollTop = box.scrollHeight;
            }
        }).always(function () {
            // Keep polling after errors too, so a restart of the miner doesn't stop the log
            if (isLogCheckboxChecked && autoUpdateLog) logTimer = setTimeout(getLog, 1000);
        });
    }

    chart.render();

    if (!localStorage.getItem("annotations")) localStorage.setItem("annotations", true);
    if (!localStorage.getItem("dark-mode")) localStorage.setItem("dark-mode", window.matchMedia("(prefers-color-scheme: dark)").matches);
    if (!localStorage.getItem("sort-by")) localStorage.setItem("sort-by", "Name ascending");

    // Restore settings from localStorage on page load
    $('#annotations').prop("checked", localStorage.getItem("annotations") === "true");
    $('#dark-mode').prop("checked", localStorage.getItem("dark-mode") === "true");

    // Handle the annotation toggle click event
    $('#annotations').click(() => {
        var isChecked = $('#annotations').prop("checked");
        localStorage.setItem("annotations", isChecked);
        updateAnnotations();
    });

    // Handle the dark mode toggle click event
    $('#dark-mode').click(() => {
        var isChecked = $('#dark-mode').prop("checked");
        localStorage.setItem("dark-mode", isChecked);
        toggleDarkMode();
    });

    $('#startDate').val(formatDate(startDate));
    $('#endDate').val(formatDate(endDate));

    sortBy = localStorage.getItem("sort-by");
    if (sortBy.includes("Points")) sortField = 'points';
    else if (sortBy.includes("Last activity")) sortField = 'last_activity';
    else sortField = 'name';
    $('#sort-select').val(sortBy);
    $('#sort-select').change(function () {
        changeSortBy($(this).val());
    });
    getStreamers();
    loadDrops();
    setInterval(loadDrops, 60000);
    loadWatching();
    setInterval(loadWatching, 15000);
    loadGames();
    setInterval(loadGames, 60000);

    updateAnnotations();
    toggleDarkMode();

    // Retrieve log checkbox state from localStorage and update UI accordingly
    var logCheckboxState = localStorage.getItem('logCheckboxState');
    $('#log').prop('checked', logCheckboxState === 'true');
    if (logCheckboxState === 'true') {
        isLogCheckboxChecked = true;
        $('#auto-update-log').show();
        $('#log-box').show();
        // Start continuously updating the log content
        getLog();
    }

    // Handle the log checkbox change event
    $('#log').change(function () {
        isLogCheckboxChecked = $(this).prop('checked');
        localStorage.setItem('logCheckboxState', isLogCheckboxChecked);

        if (isLogCheckboxChecked) {
            $('#log-box').show();
            $('#auto-update-log').show();
            getLog();
            $('html, body').scrollTop($(document).height());
        } else {
            $('#log-box').hide();
            $('#auto-update-log').hide();
            // Clear log content when checkbox is unchecked
            // $("#log-content").text('');
        }
    });
});

var watching = [];

function applyWatching() {
    $("#streamers-list li").each(function () {
        var isWatching = watching.indexOf($(this).data("user")) !== -1;
        $(this).toggleClass("is-watching", isWatching);
        $(this).attr("title", isWatching ? "Currently watching" : "");
    });
}

function loadWatching() {
    $.getJSON('./watching', function (response) {
        watching = response;
        applyWatching();
    });
}

function formatEnds(ms) {
    if (!ms) return '';
    var left = ms - Date.now();
    if (left <= 0) return 'ended';
    var days = Math.floor(left / 86400000), hours = Math.floor((left % 86400000) / 3600000);
    return (days ? days + 'd ' : '') + hours + 'h left';
}

function loadGames() {
    $.getJSON('./games', function (games) {
        var body = $('#games-body').empty();
        var picked = games.filter(function (g) { return g.prioritised; }).length;
        $('#games-count').text(games.length ? '(' + picked + ' prioritised of ' + games.length + ')' : '');
        if (!games.length) {
            body.append($('<tr>').append($('<td colspan="5" class="empty">').text('No games yet. They appear here after the first drops sync, about a minute after the miner starts.')));
            return;
        }
        games.forEach(function (g) {
            var box = $('<input type="checkbox">').prop('checked', g.prioritised).attr('aria-label', 'Prioritise ' + g.name)
                .on('change', function () { setGamePriority(g.id, this.checked, $(this)); });
            var status = $('<span class="badge">').addClass(g.active ? 'ok' : 'idle').text(g.active ? 'Offered now' : 'Not offered');
            body.append($('<tr>').toggleClass('is-prioritised', g.prioritised)
                .append($('<td>').append(box))
                .append($('<td>').text(g.name))
                .append($('<td class="muted">').text(g.campaigns || ''))
                .append($('<td class="muted">').text(g.active ? formatEnds(g.ends_at) : ''))
                .append($('<td>').append(status)));
        });
    }).fail(function () {
        $('#games-body').empty().append($('<tr>').append($('<td colspan="5" class="empty">').text('Could not load games.')));
    });
}

function setGamePriority(id, prioritised, box) {
    $.ajax({
        url: './games/' + encodeURIComponent(id) + '/priority',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ prioritised: prioritised })
    }).done(loadGames).fail(function () {
        box.prop('checked', !prioritised);  // the change was not saved
    });
}

function loadDrops() {
    $.getJSON('./drops', function (drops) {
        var body = $('#drops-body').empty();
        var claimed = drops.filter(function (d) { return d.claimed; }).length;
        $('#drops-count').text(drops.length ? '(' + claimed + ' claimed' + (drops.length > claimed ? ', ' + (drops.length - claimed) + ' failed' : '') + ')' : '');
        if (!drops.length) {
            body.append($('<tr>').append($('<td colspan="4" class="empty">').text('No drops claimed yet. Claims appear here once the miner receives a drop.')));
            return;
        }
        drops.forEach(function (d) {
            var label = d.benefit && d.benefit !== d.name ? d.name + ' (' + d.benefit + ')' : d.name;
            var status = $('<span class="badge">').addClass(d.claimed ? 'ok' : 'fail').text(d.claimed ? 'Claimed' : 'Failed');
            body.append($('<tr>')
                .append($('<td class="when">').text(new Date(d.at).toLocaleString()))
                .append($('<td>').text(label))
                .append($('<td>').text(d.game || ''))
                .append($('<td>').append(status)));
        });
    }).fail(function () {
        $('#drops-body').empty().append($('<tr>').append($('<td colspan="4" class="empty">').text('Could not load drops.')));
    });
}

function formatDate(date) {
    var d = new Date(date),
        month = '' + (d.getMonth() + 1),
        day = '' + d.getDate(),
        year = d.getFullYear();

    if (month.length < 2) month = '0' + month;
    if (day.length < 2) day = '0' + day;

    return [year, month, day].join('-');
}

function changeStreamer(streamer, index) {
    $("#streamers-list li").removeClass("is-active")
    $("#streamers-list li").eq(index - 1).addClass('is-active');
    currentStreamer = streamer;

    // Update the chart title with the current streamer's name
    options.title.text = `${streamer.replace(".json", "")}'s channel points (dates are displayed in UTC)`;
    chart.updateOptions(options);

    // Save the selected streamer in localStorage
    localStorage.setItem("selectedStreamer", currentStreamer);

    getStreamerData(streamer);
}

function getStreamerData(streamer) {
    if (currentStreamer == streamer) {
        $.getJSON(`./json/${streamer}`, {
            startDate: formatDate(startDate),
            endDate: formatDate(endDate)
        }, function (response) {
            chart.updateSeries([{
                name: streamer.replace(".json", ""),
                data: response["series"]
            }], true)
            clearAnnotations();
            annotations = response["annotations"];
            updateAnnotations();
            setTimeout(function () {
                getStreamerData(streamer);
            }, 300000); // 5 minutes
        });
    }
}

function getAllStreamersData() {
    $.getJSON(`./json_all`, function (response) {
        for (var i in response) {
            chart.appendSeries({
                name: response[i]["name"].replace(".json", ""),
                data: response[i]["data"]["series"]
            }, true)
        }
    });
}

function getStreamers() {
    $.getJSON('streamers', function (response) {
        streamersList = response;
        sortStreamers();

        // Restore the selected streamer from localStorage on page load
        var selectedStreamer = localStorage.getItem("selectedStreamer");

        if (selectedStreamer) {
            currentStreamer = selectedStreamer;
        } else {
            // If no selected streamer is found, default to the first streamer in the list
            currentStreamer = streamersList.length > 0 ? streamersList[0].name : null;
        }

        // Ensure the selected streamer is still active and scrolled into view
        renderStreamers();
    });
}

function renderStreamers() {
    $("#streamers-list").empty();
    var promised = new Promise((resolve, reject) => {
        streamersList.forEach((streamer, index, array) => {
            displayname = streamer.name.replace(".json", "");
            if (sortField == 'points') displayname = displayname + "<span class='meta'>" + streamer['points'] + "</span>";
            else if (sortField == 'last_activity') displayname = displayname + "<span class='meta'>" + formatDate(streamer['last_activity']) + "</span>";
            var isActive = currentStreamer === streamer.name;
            if (!isActive && localStorage.getItem("selectedStreamer") === null && index === 0) {
                isActive = true;
                currentStreamer = streamer.name;
            }
            var activeClass = isActive ? 'is-active' : '';
            var listItem = `<li id="streamer-${streamer.name}" data-user="${streamer.name.replace(".json", "")}" class="${activeClass}"><a onClick="changeStreamer('${streamer.name}', ${index + 1}); return false;">${displayname}</a></li>`;
            $("#streamers-list").append(listItem);
            if (isActive) {
                // Scroll the selected streamer into view
                document.getElementById(`streamer-${streamer.name}`).scrollIntoView({
                    behavior: 'smooth',
                    block: 'center'
                });
            }
            if (index === array.length - 1) resolve();
        });
    });
    promised.then(() => {
        applyWatching();
        changeStreamer(currentStreamer, streamersList.findIndex(streamer => streamer.name === currentStreamer) + 1);
    });
}

function sortStreamers() {
    streamersList = streamersList.sort((a, b) => {
        return (a[sortField] > b[sortField] ? 1 : -1) * (sortBy.includes("ascending") ? 1 : -1);
    });
}

function changeSortBy(value) {
    sortBy = value;
    if (sortBy.includes("Points")) sortField = 'points'
    else if (sortBy.includes("Last activity")) sortField = 'last_activity'
    else sortField = 'name';
    sortStreamers();
    renderStreamers();
    localStorage.setItem("sort-by", sortBy);
}

function updateAnnotations() {
    if ($('#annotations').prop("checked") === true) {
        clearAnnotations()
        if (annotations && annotations.length > 0)
            annotations.forEach((annotation, index) => {
                annotations[index]['id'] = `id-${index}`
                chart.addXaxisAnnotation(annotation, true)
            })
    } else clearAnnotations()
}

function clearAnnotations() {
    if (annotations && annotations.length > 0)
        annotations.forEach((annotation, index) => {
            chart.removeAnnotation(annotation['id'])
        })
    chart.clearAnnotations();
}

// Input date
$('#startDate').change(() => {
    startDate = new Date($('#startDate').val());
    getStreamerData(currentStreamer);
});
$('#endDate').change(() => {
    endDate = new Date($('#endDate').val());
    getStreamerData(currentStreamer);
});
