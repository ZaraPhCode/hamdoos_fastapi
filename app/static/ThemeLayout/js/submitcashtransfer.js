const submit_link = $('#submit_link').val()

function showTotalPrice() {
    let reference = $('#OrderId').val();
    let selectedOption = $("#OrderId option[value='" + reference + "']").get(0);
    var price = $(selectedOption).data("price");
    //let total_paid_tax_excl = $('#total_paid_tax_excl' + reference).val();
    //if (reference != 0) {
    //    total_paid_tax_excl = parseInt(total_paid_tax_excl);
    //}
    $('#price').val(price);
}

kamaDatepicker('date', {
    forceFarsiDigits: true
    , markToday: true
    , markHolidays: true
    , highlightSelectedDay: true
    , sync: true
    , pastYearsCount: 0
    , futureYearsCount: 3
    , swapNextPrev: true
});

Dropzone.autoDiscover = false;

let myDropzone = new Dropzone("div#design-image", {
    autoProcessQueue: false,
    url: submit_link,
    paramName: "file",
    previewsContainer: '.dropzone-previews',
    maxFilesize: 2,
    addRemoveLinks: true,
    maxFiles: 1,
    parallelUploads: 1,
    dictRemoveFile: "حذف فایل",
    dictFileTooBig: "حجم فایل باید کمتر از ۱ مگابایت باشد"
});

myDropzone.on("maxfilesexceeded", function (file) {
    myDropzone.removeFile(file);
});


$('[name=submit_cash_transfer]').click(function (e) {
    $.confirm({
        title: 'تائید',
        content: 'آیا مطمئن هستید؟',
        buttons: {
            confirm: {
                text:"بله",
                action: function () {
                    registerReceipt(e);
                    //$.alert('Confirmed!');
                }
            },
            cancel: {
                text: "خیر",
                action: function () {
                }
            },
        }
    });
});
function registerReceipt(e) {
    let formData = new FormData(document.getElementById('form_id'));
    let tab_value = $('#tab_value').val()
    let err = ''
    formData.append('action', 'submit_cash_transfer');
    formData.append('tab', tab_value);
    let data = myDropzone.getAcceptedFiles();
    $.each(data, function (key, el) {
        formData.append('img', el);
    });

    $.ajax({
        url: submit_link,
        data: formData,
        type: "POST",
        async: false,
        cache: false,
        contentType: false,
        enctype: 'multipart/form-data',
        processData: false,
        dataType: "json",
        success: function (res) {
            if ((res.success).length !== 0) {
                $('#result_alert .modal-body').html('<i class="fa fa-check "></i>' + ' ' + res.success)
            } else {
                $.each(res.errors, function (key, el) {
                    err = err + el + '<br>';
                });
                $('#result_alert .modal-body').html('<i class="fa fa-remove"></i>' + ' ' + err)
            }
        },
        fail: function (res) {
            $.each(res.errors, function (key, el) {
                err = err + el + '<br>';
            });
            $('#result_alert .modal-body').html('<i class="fa fa-remove"></i>' + ' ' + err)
        },
        complete: () => {
            $('#result_alert').modal('show')
            $('#order_reference').val('')
            $('#bank').val(0)
            $('#price').val('')
            $('#date').val('')
            $("#description").val('');
            $('#paya_draft_yes').prop('checked', false);
            $('#paya_draft_no').prop('checked', true);
        }
    });
}