function FillCategories(data) {
    var categoryTree = $("#CategoryTree");
    categoryTree.append('<ul class="g-tp__source g-rf__target" id="filter-picker" aria-expanded="true" role="tree"></ul>');

    for (var i = 0; i < data.length; i++) {
        createTree(data[i], null);
    }
}

function createTree(node, parent) {
    var listItem = $("<li>", { role: "treeitem" });
    if (node.childs && node.childs.length > 0) {
        var buttonPlus = $("<button>", { type: "button", class: "g-tp__navigator" }).text("+");
        var buttonValue = $("<button>", { type: "button", id: node.id, class: "g-tp__value" }).text(node.title);
        listItem.append(buttonPlus);
        listItem.append(buttonValue);
    }
    else {
        var buttonPlus = $("<button>", { type: "button", class: "g-tp__navigator" }).text("o");
        var buttonValue = $("<button>", { type: "button", id: node.id, class: "g-tp__value" }).text(node.title);
        listItem.append(buttonPlus);
        listItem.append(buttonValue);
    }

    if (node.childs && node.childs.length > 0) {
        var childList = $("<ul>", { role: "group" });
        $.each(node.childs, function (index, childNode) {
            createTree(childNode, childList);
        });
        listItem.append(childList);
    }

    if (parent) {
        parent.append(listItem);
    } else {
        $("#filter-picker").append(listItem);
    }
}

var juis = {
    //hide/show an element using aria properties
    setVisibility: function (element, visible) {
        element.setAttribute("aria-hidden", !visible);
    },
    setExpandedState: function (element, expanded) {
        element.setAttribute("aria-expanded", !expanded);
    },
    sanitiseRegEx: function (s) {
        return s.replace(/[-\\^$*+?.()|[\]{ }]/g, "\\$&");
    },
    keyModiferActive: function (event) {
        return event.altKey ||
            event.ctrlKey ||
            event.metaKey ||
            event.shiftKey;
    },
};

juis.treePicker = (function () {
    /* Properties */
    var _currentPicker;

    var _classes = {
        navigator: "g-tp__navigator",
        itemHasChildren: "g-tp__item--hasChildren",
        itemValue: "g-tp__value",
    };

    /* Constructor Helpers */

    // First run setup
    function _setup(target) {
        var tree = document.querySelector("#" + target);
        var treeValues = tree.querySelectorAll(".g-tp__value");

        //reverse loop through nodes to process from children up (and not parents down)
        for (var i = treeValues.length - 1; i > -1; i--) {
            //set data value
            _addToDataSet(treeValues[i].parentNode, treeValues[i].textContent);
            //store original value
            treeValues[i].dataset.originalValue = treeValues[i].textContent;

            //add flter values to parent
            //select parent
            var parentItem = treeValues[i].parentNode.parentNode;
            var parentValue = parentItem.parentNode.querySelector(".g-tp__value");
            //ensure we're not at the top
            if (parentItem !== tree && parentValue) {
                //set parent data value
                _addToDataSet(parentValue.parentNode, treeValues[i].parentNode.dataset.searchValue);
            }
        }

        //mark and collapse branches
        var branches = tree.querySelectorAll("[role='group']");//ARIA calls branches "groups" for reasons unknown
        for (i = 0; i < branches.length; i++) {
            //mark parent as having children
            branches[i].parentNode.classList.add(_classes.itemHasChildren);

            //collapse
            juis.setExpandedState(branches[i], true);
        }

        //prevent tab focus on buttons
        var buttons = tree.querySelectorAll("button");

        for (i = 0; i < buttons.length; i++) {
            buttons[i].setAttribute("tabindex", -1);
        }

        //clone the tree and attach it to the to the original
        //tree.clone = tree.cloneNode(true);
    }

    // Event binding
    function _bind(picker, target) {
        //initialise events
        picker.addEventListener("focus", _setPicker);
        picker.addEventListener("input", _applyFilter);
        picker.addEventListener("keydown", _handleKeyboardEvents);

        var tree = document.querySelector("#" + target);
        var navigators = tree.querySelectorAll(_getClassSelector(_classes.itemHasChildren) + " > " + _getClassSelector(_classes.navigator));

        for (var i = 0; i < navigators.length; i++) {
            //filter out elements without children
            //      var child = navigators[i].parentNode.classList.contains(_classes.itemHasChildren);
            //      if (!child) {
            //        continue;
            //      }

            //add click event
            navigators[i].addEventListener("click", _toggleChild);
        }

        var treeNodes = tree.querySelectorAll(".g-tp__value");

        for (i = 0; i < treeNodes.length; i++) {
            //add select event
            treeNodes[i].addEventListener("click", _clickNode);
        }
    }

    /* Event Handlers */

    function _applyFilter(event) {
        var target = event.target.dataset.target;
        var tree = document.querySelector("#" + target);

        _resetTree(tree);

        //don't filter for less than two characters
        var filterValue = this.value.toLowerCase();
        if (filterValue.length < 2) {
            _clearFilters(tree);
            return;
        }

        //select non-matching elements
        var selected = tree.querySelectorAll("li:not([data-search-value*='" + filterValue + "'])");

        //hide non-matching nodes
        for (var i = 0; i < selected.length; i++) {
            juis.setVisibility(selected[i]);
        }

        //select matching elements
        var matches = tree.querySelectorAll("li[data-search-value*='" + filterValue + "'] ." + _classes.itemValue);

        //highlight matching text
        for (i = 0; i < matches.length; i++) {
            matches[i].innerHTML = matches[i].dataset.originalValue.replace(new RegExp(juis.sanitiseRegEx(filterValue), "gi"), "<mark>$&</mark>");
        }

        //fully expand the tree to show matching nodes
        _toggleChildren(tree, true);
    }

    //set picker value
    function _clickNode(event) {
        $(_currentPicker).attr("data-category-id", event.target.id);
        //$(_currentPicker).val(event.target.id);
        _setValue(event.target.textContent);
    }

    //select node by keyboard
    function _selectNode(event) {
        var selectedNode = document.querySelector("#" + event.target.dataset.target + " [aria-selected='true'] .g-tp__value");

        $(_currentPicker).attr("data-category-id", $(selectedNode).attr("id"));

        _setValue(selectedNode.textContent);
    }

    //set target picker
    function _setPicker(event) {
        _currentPicker = event.target;
    }

    function _handleKeyboardEvents(event) {
        //ignore keys if modifiers are active
        if (juis.keyModiferActive(event)) {
            return;
        }

        var code = event.key || event.charCode || event.keyCode;

        switch (code) {
            case "ArrowDown":
            case 40:
                _go(event.target, "down");
                event.preventDefault();
                break;
            case "ArrowUp":
            case 38:
                _go(event.target, "up");
                event.preventDefault();
                break;
            case "ArrowLeft":
            case 37:
                //if filtered, break
                _go(event.target, "out");
                event.preventDefault();
                break;
            case "ArrowRight":
            case 39:
                //if filtered, break
                _go(event.target, "in");
                event.preventDefault();
                break;
            case "Enter":
            case "13":
                //handle return to select
                _selectNode(event);
                break;
            default:
        }
    }

    function _toggleChild() {
        // toggle child expanded state
        var child = this.parentNode.querySelector("[role='group']");
        juis.setExpandedState(child, child.hasAttribute("aria-expanded") && child.getAttribute("aria-expanded") === "true");
    }

    /* Methods */

    //adds a search value to a element's data set
    function _addToDataSet(element, value) {
        var elementData = [];
        //fetch any existing values
        if (element.dataset.searchValue) {
            elementData = element.dataset.searchValue.split(",");
        }
        //add the new one
        elementData.push(value.toLowerCase());
        //return to the element
        element.dataset.searchValue = elementData.join();
    }

    //reset the tree to it's original layout
    function _resetTree(tree) {
        //select items
        var items = tree.querySelectorAll(".g-tp__value");

        //show everything by default (reset)
        for (var i = 0; i < items.length; i++) {
            juis.setVisibility(items[i].parentNode, true);
        }

        //Deselect any selected nodes
        var selected = tree.querySelector("[aria-selected='true']");
        if (!selected) {
            return;
        }
        selected.setAttribute("aria-selected", "false");
    }

    //clear marks, collapse
    function _clearFilters(tree) {
        //collapse the tree
        _toggleChildren(tree);

        //clear highlights
        var highlights = tree.querySelectorAll("mark");
        for (var i = 0; i < highlights.length; i++) {
            highlights[i].outerHTML = highlights[i].outerHTML.replace(/<.*>(.*)<.*>/, "$1");
        }
    }

    function _getClassSelector(className) {
        return "." + className;
    }

    function _getTree(id) {
        return document.querySelector("#" + id);
    }

    //hide/show all children in the tree
    function _toggleChildren(tree, hide) {
        var parents = tree.querySelectorAll(_getClassSelector(_classes.itemHasChildren));
        for (var i = 0; i < parents.length; i++) {
            juis.setExpandedState(parents[i].querySelector("[role='group']"), !hide);
        }
    }

    function _setValue(value) {
        if (!_currentPicker) {
            throw new Error("Tree Picker failed to set target");
        }

        //set value
        _currentPicker.value = value;

        //return focus to the picker
        _currentPicker.focus();

        //select tree
        var tree = document.querySelector("#" + _currentPicker.dataset.target);

        //hide tree
        juis.richField.hide(tree);

        //reset positioning, clear filters,
        _resetTree(tree);
        _clearFilters(tree);
    }

    //handles keyboard navigation
    function _go(field, direction) {
        //get selected node
        var tree = document.querySelector("#" + field.dataset.target);
        var selectedNode = tree.querySelector("[aria-selected='true']");

        //if no selected node
        if (!selectedNode) {
            //if down, select first visible
            if (direction !== "down") {
                return;
            }

            var firstNode = tree.querySelector("li:not([aria-hidden='true'])");
            if (!firstNode) {//if none are visible, exit
                return;
            }

            //set highlight
            firstNode.setAttribute("aria-selected", "true");
            return;
        }

        //if filter has been applied, ignore in/out
        switch (direction) {
            case "in":
                // if selected node has collapsed children, expand them
                var childTree = selectedNode.querySelector("[role='group']");
                if (childTree && childTree.getAttribute("aria-expanded") === "false") {
                    childTree.setAttribute("aria-expanded", "true");
                }
                break;
            case "out":
                // if selected node has expanded children, collapse them
                childTree = selectedNode.querySelector("[role='group']");
                if (childTree && childTree.getAttribute("aria-expanded") === "true") {
                    childTree.setAttribute("aria-expanded", "false");
                    return;
                }

                //if a parent group exists, collapse the group
                var parentRole = selectedNode.parentNode.getAttribute("role");
                if (parentRole && parentRole === "group") {
                    selectedNode.parentNode.setAttribute("aria-expanded", "false");

                    //clear child selection
                    selectedNode.setAttribute("aria-selected", "false");

                    //select the parent node
                    selectedNode.parentNode.parentNode.setAttribute("aria-selected", "true");
                }
                break;
            case "up":
            case "down":
                //fetch visible nodes
                var visibleNodes = tree.querySelectorAll("[aria-expanded='true'] > li:not([aria-hidden='true'])");
                var selectedNodeIndex;
                //loop through nodes and find the currently selected node
                for (var i = 0; i < visibleNodes.length; i++) {
                    //keep looking until we find the selected node in the list
                    if (visibleNodes[i] !== selectedNode) {
                        continue;
                    }

                    selectedNodeIndex = i;
                    break;
                }

                //if we're at the first and want to go up
                //or we're at the last and want to go down
                if (selectedNodeIndex === 0 && direction === "up" ||
                    selectedNodeIndex === (visibleNodes.length - 1) && direction === "down") {
                    //do nothing
                    return;
                }
                selectedNode.setAttribute("aria-selected", "false");
                //select previous/next node
                selectedNodeIndex = selectedNodeIndex + (direction === "down" ? 1 : -1);
                //if there are no selectable nodes
                if (!visibleNodes[selectedNodeIndex]) {
                    return;
                }
                visibleNodes[selectedNodeIndex].setAttribute("aria-selected", "true");
                return;
            default:
        }
    }

    /* Public Methods */
    return {
        init: function () {
            var treePickers = document.querySelectorAll(".g-tp");

            for (var i = 0; i < treePickers.length; i++) {
                var target = treePickers[i].dataset.target;
                _setup(target);
                _bind(treePickers[i], target);
            }
        }
    };

})();

// Rich Field control for enhancing form fields
// Handles hide/show/focus events
juis.richField = (function () {
    /* Properties */
    var _targetHasFocus = false;

    /* Constructor Helpers */

    function _setup(field) {
        _hide(_getTargetElement(field.dataset.target));
    }

    function _bind(field) {
        var target = _getTargetElement(field.dataset.target);
        //hide on esc
        window.addEventListener("keydown", function (event) {
            var code = event.key || event.charCode || event.keyCode;

            if (code && (code === "Escape" || code === 27)) {//esc
                _hide(target);
            }
        });

        //hide when anything outside the target is clicked
        document.addEventListener("click", function (event) {
            if (event.target !== field) {
                _hide(target);
            }
            _targetHasFocus = false;
        });

        //mark when target has focus
        target.addEventListener("mousedown", function (event) {
            _targetHasFocus = true;
            event.stopPropagation();
        });

        //mark when target has focus
        target.addEventListener("click", function (event) {
            _targetHasFocus = true;
            //prevent click event from going any further
            event.stopPropagation();
        });

        //mark when target has focus
        target.addEventListener("focus", function (event) {
            _targetHasFocus = true;
        });

        //mark when target has focus
        target.addEventListener("blur", function (event) {
            _targetHasFocus = false;
        });

        //show on element focus
        field.addEventListener("focus", function () {
            _show(target);
        });

        //show on element click
        field.addEventListener("click", function () {
            _show(target);
        });

        //show on element keydown
        field.addEventListener("keydown", function (event) {
            //ignore keys if modifiers are active
            if (juis.keyModiferActive(event)) {
                return;
            }

            var code = event.key || event.charCode || event.keyCode;

            //if not an up, left or right arrow key, enter or tab
            switch (code) {
                case "ArrowUp":
                case 38:
                case "ArrowLeft":
                case 37:
                case "ArrowRight":
                case 39:
                case "Enter":
                case "13":
                case "Tab":
                case "9":
                case "Escape":
                case "27":
                    return;
                default:
            }

            _show(target);
        });

        //hide on element blur if target doesn't have focus
        field.addEventListener("blur", function () {
            //use a timeout to allow the target element's click event to kick in
            window.setTimeout(function () {
                if (!_targetHasFocus) {
                    _hide(target);
                }
            }, 150);
        });
    }

    /* Event Handlers */

    function _hide(target) {
        juis.setVisibility(target);
    }

    function _show(target) {
        juis.setVisibility(target, true);
        $("#filter-picker").css({
            'position': 'absolute',
            'z-index': '100',
            'background-color': 'aliceblue',
            'width': '-webkit-fill-available',
        });
    }

    function _getTargetElement(target) {
        return document.querySelector("#" + target);
    }

    /* Public Methods */
    return {
        init: function () {
            var fields = document.querySelectorAll(".g-rf");
            for (var i = 0; i < fields.length; i++) {
                _setup(fields[i]);
                _bind(fields[i]);
            }
        },
        show: function (target) {
            _show(target);
        },
        hide: function (target) {
            _hide(target);
        }
    };
})();