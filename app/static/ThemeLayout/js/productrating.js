$(document).ready(() => {

    let rateAvg = (typeof productRatingAverage === 'undefined' || productRatingAverage.length <= 0) ? 0 : productRatingAverage;
    let userRate = (typeof currentUserRate === 'undefined' || currentUserRate.length <= 0) ? 0 : currentUserRate;
    $("#rateYo").rateYo({
        rating: rateAvg,
        fullStar: true,
        starWidth: '15px',
        ratedFill: '#ffd21f',
        readOnly: true,
    });

    $("#product-comment-rate").rateYo({
        rating: userRate,
        fullStar: true,
        starWidth: '25px',
        ratedFill: '#ffd21f',
        onSet: function (rating, rateYoInstance) {
            submitProductRating(rating);
        },
        // onChange: function (rating, rateYoInstance) {
        //     $(this).next().text(rating);
        // }
    });

});

function submitProductRating(rating) {
    $.ajax({
        type: 'POST',
        url: productRatingActionLink,
        data: {
            ajax: true,
            id_product: productRatingIdProduct,
            rating: rating
        },
        success: function(res) {
            if (res.success === true) {
                showRatingMessage('امتیاز با موفقیت ثبت شد');
            } else {
                showRatingMessage(res.error);
            }
        },
        error: function(err) {
            showRatingMessage('مشکلی در ثبت امتیاز پیش آمد');
        }
    });
}

function showRatingMessage(message) {
    let rating_message_container = $("#rating-message-container");
    rating_message_container.empty().html(message).show(200, () => {
        setTimeout(() => {
            rating_message_container.hide(500);
        }, 3000)
    });
}