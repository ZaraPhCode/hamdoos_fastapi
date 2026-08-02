$(document).ready(function () {
    $(document).on('submit', '#create', function (e) {
        e.preventDefault();
        submitFunction('create');
    });
    //$(document).on('click', '#resend', function (e) {
    //    e.preventDefault();
    //    $('input[name=force_sms]').val(1);
    //    $('input[name=account_type]').appendTo($('#hidden-create form'));
    //    submitFunction('create');
    //});
    $(document).on('click', '#reverse', function (e) {
        e.preventDefault();
        $('input[name=ReverseSMS]').val('1');
        submitFunction('verify');
    });
    $(document).on('submit', '#login', function (e) {
        e.preventDefault();
        submitFunction('login');
    });
    //$(document).on('submit', '#verify', function (e) {
    //    e.preventDefault();
    //    submitFunction('verify');
    //});
    $(document).on('submit', '#account-creation_form', function (e) {
        e.preventDefault();
        submitFunction('account-creation_form');
    });

    $(document).on('click', 'span.verify', function (e) {
        e.preventDefault();
        $('input[name=phone_mobile]').val($(this).closest('h4').find('span.phone').text());
        submitFunction('create', $(this).data("addressid"));
    });

    $(document).on('click', '#SubmitSMSPassword', function (e) {
        e.preventDefault();
        $('input[name=phone_mobile]').val($(this).find('span.phone').text());
        $('input[name=force_sms]').val(1);
        $('input[name=account_type]').appendTo($('#hidden-create form'));
        $('input[name=force_sms]').appendTo($('#hidden-create form'));
        submitFunction('create');
    });

    $(document).on('click', 'span.delete', function (e) {
        e.preventDefault();
        deleteFunction(this);
    });
    $('.is_customer_param').hide();
});

function submitFunction(form, address) {
    $('#' + form + '_error').html('').hide();
    var data = {
        //controller: 'authentication',
        // SubmitCheck: 1,
        //ajax: true,
        //phone_mobile: $('#phone_mobile').val(),
        phoneNumber: $('#phone_mobile').val(),
        addressId: address,
        back: $('input[name=back]').val(),
        //token: token
    };

    //data['fc'] = 'module';
    //data['module'] = 'iverify';

    //if (form === 'account-creation_form') {
    //    data['submitAccount'] = 1;
    //}
    $('#' + form).find('input').each(function () {
        if (this.type === 'radio' && !this.checked) {
            return true;
        }
        data[this.name] = this.value;
    });
    $('#' + form + ' button').attr('disabled', 'disabled');
    $.ajax({
        type: 'POST',
        url: "/Shop/Profile/VerifyPhoneNumber",
        async: true,
        cache: false,
        dataType: "json",
        //headers: {"cache-control": "no-cache"},
        data: data,
        success: function (jsonData) {
            if (!jsonData.hasError && jsonData.redirect) {
                //console.log(redirectURL);
                window.location.href = jsonData.redirectURL;
            } else if (jsonData.hasError) {
                var errors = '';
                for (error in jsonData.errors)
                    //IE6 bug fix
                    if (error != 'indexOf')
                        errors += '<li>' + jsonData.errors[error] + '</li>';
                $('#' + form + '_error').html('<ol>' + errors + '</ol>').show();
                $('#' + form + ' button').attr('disabled', false);

            } else {
                // adding a div to display a transition
                $('#center_column').html('<div id="noSlide">' + $('#center_column').html() + '</div>');
                $('#content').html('<div id="noSlide">' + $('#content').html() + '</div>');
                $('#noSlide').fadeOut('slow', function () {
                    $('#noSlide').html(jsonData.page);
                    $(this).fadeIn('slow', function () {
                        if (typeof bindUniform !== 'undefined')
                            bindUniform();
                        if (typeof bindStateInputAndUpdate !== 'undefined')
                            bindStateInputAndUpdate();
                        document.location = '#account-creation';
                    });
                });
            }
        },
        error: function (XMLHttpRequest, textStatus, errorThrown) {
            error = "TECHNICAL ERROR: unable to load form.\n\nDetails:\nError thrown: " + XMLHttpRequest + "\n" + 'Text status: ' + textStatus;
            if (!!$.prototype.fancybox) {
                $.fancybox.open([
                        {
                            type: 'inline',
                            autoScale: true,
                            minHeight: 30,
                            content: "<p class='fancybox-error'>" + error + '</p>'
                        }],
                    {
                        padding: 0
                    });
            } else
                alert(error);
        }
    });
    if (typeof sms_resend == 'undefined' || sms_resend == 0) {
        resend_time = ':10';
    } else {
        resend_time = sms_resend + ':00';
    }

}

function deleteFunction(element) {
    // console.log(this.id);
    var data = {
        //controller: 'authentication',
        //fc: 'module',
        //module: 'iverify',
        //SubmitDelete: 1,
        //ajax: true,
        Id : element.id
        //id_phone: element.id,
        //token: token
    };

    $.ajax({
        type: 'POST',
        //url: baseUri + '?rand=' + new Date().getTime(),
        ulr: "Profile/DeletePohoneNumber",
        async: true,
        cache: false,
        dataType: "json",
        headers: {"cache-control": "no-cache"},
        data: data,
        success: function (jsonData) {
            if (jsonData.hasError == true) {
                var errors = '';
                for (error in jsonData.errors)
                    //IE6 bug fix
                    if (error != 'indexOf')
                        errors += '<li>' + jsonData.errors[error] + '</li>';

                $('#number_error').html('<ol>' + errors + '</ol>').show();
            } else {
                // adding a div to display a transition
                //$('#center_column').html('<div id="noSlide">' + $('#center_column').html() + '</div>');
                //$('#content').html('<div id="noSlide">' + $('#content').html() + '</div>');
                $(element).parent().fadeOut('slow', function () {

                    // $('#noSlide').html(jsonData.page);

                });
            }
        },
        error: function (XMLHttpRequest, textStatus, errorThrown) {
            error = "TECHNICAL ERROR: unable to load form.\n\nDetails:\nError thrown: " + XMLHttpRequest + "\n" + 'Text status: ' + textStatus;
            if (!!$.prototype.fancybox) {
                $.fancybox.open([
                        {
                            type: 'inline',
                            autoScale: true,
                            minHeight: 30,
                            content: "<p class='fancybox-error'>" + error + '</p>'
                        }],
                    {
                        padding: 0
                    });
            } else
                alert(error);
        }
    });
}

function resendSMS() {
    submitFunction('create');
}

function changeNumber() {
    const form = $('#hidden-create form');
    $('#login_form').fadeOut('slow', function () {
        $(this).replaceWith(form);
    })
}