$(document).ready(function () {
    $('#invoice-option-check').change(function() {
        let invoiceRequired = 0;
        if(this.checked) {
            // add order invoice
            invoiceRequired = 1;
        }

        $.ajax({
            type: 'POST',
            headers: { "cache-control": "no-cache" },
            url: orderInvoiceOptionCheckUrl + '?rand=' + new Date().getTime(),
            async: true,
            cache: false,
            dataType : "json",
            data: 'ajax=true&method=invoiceRequirement' + '&required=' + invoiceRequired + '&token=' + static_token,
            success: function(jsonData)
            {
                if(jsonData.status == false) {
                    alert('مشکلی در درخواست فاکتور پیش آمد');
                }
            },
            error: function(XMLHttpRequest, textStatus, errorThrown) {
            }
        });
    });
});

function notifyMe() {

    //let email = $("#notify_email").val();

    $.ajax({
        type: 'POST',
        headers: { "cache-control": "no-cache" },
        url: stockNotificationNotifyMeUrl,
        async: true,
        cache: false,
        dataType : "json",
        data:  'id=' + stockNotificationIdProduct,
        success: function(jsonData)
        {
            if(jsonData.status === false) {
                alert(jsonData.error);
            } else {
                $("#stock-notification-div").css({'display': 'none'});
                $("#stock-notification-message").css({'display': 'block'}).html('<p class="text-success"><i class="fa fa-bell"></i> در صورت تجدید موجودی به شما اطلاع خواهیم داد.</p>');
            }
            console.log(jsonData);
        },
        error: function (XMLHttpRequest, textStatus, errorThrown) {
            console.log(XMLHttpRequest);
        }
    });
}