var resend_time = "02:30";
$(document).ready(function () {
    $('#resend').hide();
    $('.resendsms ').hide();
// timer
    verifyTimer();
});
function verifyTimer() {
    $('#timerofsendcode').show();
    $('#resend').hide();
    // var timer2 = "0:20";
    var interval = setInterval(function () {
        var timer = resend_time.split(':');
        //by parsing integer, I avoid all extra string processing
        var minutes = parseInt(timer[0], 10);
        var seconds = parseInt(timer[1], 10);
        --seconds;
        minutes = (seconds < 0) ? --minutes : minutes;
        seconds = (seconds < 0) ? 59 : seconds;
        seconds = (seconds < 10) ? '0' + seconds : seconds;
        //minutes = (minutes < 10) ?  minutes : minutes;
        $('.countdown').html(minutes + ':' + seconds);
        $('.inputcountdown').val(minutes + seconds);
        if (minutes < 0) clearInterval(interval);
        //check if both minutes and seconds are 0
        if ((seconds <= 0) && (minutes <= 0)) clearInterval(interval);
        resend_time = minutes + ':' + seconds;
        if (seconds <= 0 && minutes <= 0) {
            $('#timerofsendcode').hide();
            $('#resend').show();
        }
    }, 1000);
}