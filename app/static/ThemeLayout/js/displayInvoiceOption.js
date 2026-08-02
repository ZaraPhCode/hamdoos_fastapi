$(document).ready(function () {


    $("#invoice-required").on('click', function () {
        let invoice_required = $("#invoice-required").is(':checked');
        // send invoice_required to front controller in invoice option module
        $.ajax({
            type: 'POST',
            headers: { "cache-control": "no-cache" },
            url: invoiceOptionUrl + '?rand=' + new Date().getTime(),
            async: true,
            cache: false,
            dataType : "json",
            // data: 'ajax=true&method=toggleOption' + '&token=' + static_token ,
            data: {
                ajax: true,
                method: 'toggleOption',
                token: invoiceOptionToken,
                invoice_required: invoice_required
            } ,
            success: function(jsonData)
            {
                if(jsonData.status === false) {
                    alert(jsonData.error);
                } else {
                    $("#stock-notification-div").css({'display': 'none'});
                    $("#stock-notification-message").css({'display': 'block'}).html('<p class="text-success"><i class="fa fa-bell"></i> در صورت تجدید موجودی به شما اطلاع خواهیم داد</p>');
                }
            },
            error: function(XMLHttpRequest, textStatus, errorThrown) {
            }
        });
    });


});