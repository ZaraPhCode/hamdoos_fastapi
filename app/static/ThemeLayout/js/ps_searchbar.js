$(document).ready(function () {
    var $searchWidget = $('#search_widget');
    var $searchBox = $searchWidget.find('input[type=text]');
    var searchURL = $searchWidget.attr('data-search-controller-url');

    $.widget('prestashop.psBlockSearchAutocomplete', $.ui.autocomplete, {
        _renderItem: function (ul, product) {
            var cover = '', ref = '';
            if (product.featureImageURL) {
                cover = $('<span>').addClass('cover').html('<img src="/' + product.featureImageURL +'" class="img-fluid">');
            }
            if (product.partNumber && product.partNumber != '') {
                ref = $('<span>').addClass('pref').html(' (Ref: ' + product.partNumber + ')');
            }

            return $('<li>').addClass('search-menu-item')
                .append($('<a href="/products/' + (product.slug || product.partNumber) + '">').addClass('search-item')
                    .append(cover)
                    .append($('<span>').addClass('info')
                        .append($('<span>').html(product.name).addClass('product'))
                        .append($('<span>').html(product.price).addClass('pprice'))
                        .append(ref)
                    )
                ).appendTo(ul)
            ;
        }
    });

    $searchBox.psBlockSearchAutocomplete({
        source: function (query, response) {
            $.post(searchURL, {
                q: query.term,
                resultsPerPage: 10
            }, null, 'json')
            .then(function (resp) {
                response(resp.products);
            })
            .fail(function (jqXHR, textStatus, errorThrown) {
                console.error('Search Error Details:', {
                    status: textStatus,
                    error: errorThrown,
                    statusCode: jqXHR.status,
                    response: jqXHR.responseText
                });
                response([]);
            });
        },
        select: function (event, ui) {
            var dest = ui.item.slug || ui.item.partNumber;
            window.location.href = "/products/" + dest;
        },
    });

    // Enable the same live autocomplete on the mobile search panel.
    var $mobileSearch = $('#mobile-search-panel input[type=text]');
    if ($mobileSearch.length) {
        $mobileSearch.psBlockSearchAutocomplete({
            source: function (query, response) {
                $.post(searchURL, {
                    q: query.term,
                    resultsPerPage: 10
                }, null, 'json')
                .then(function (resp) {
                    response(resp.products);
                })
                .fail(function () {
                    response([]);
                });
            },
            select: function (event, ui) {
                var dest = ui.item.slug || ui.item.partNumber;
                window.location.href = "/products/" + dest;
            },
        });
    }
});
