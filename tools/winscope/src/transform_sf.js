/*
 * Copyright 2017, The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import {transform, nanos_to_string, get_visible_chip} from './transform.js'

const FLAG_HIDDEN = 0x1;
var RELATIVE_Z_CHIP = {short: 'RelZ',
    long: "Is relative Z-ordered to another surface",
    class: 'warn'};
var RELATIVE_Z_PARENT_CHIP = {short: 'RelZParent',
    long: "Something is relative Z-ordered to this surface",
    class: 'warn'};
var MISSING_LAYER = {short: 'MissingLayer',
    long: "This layer was referenced from the parent, but not present in the trace",
    class: 'error'};

function transform_layer(layer, {parentBounds, parentHidden}) {

  function get_bounds(layer) {
    var size = layer.size || {w: 0, h: 0};
    return {
      left: 0,
      right: size.w,
      top: 0,
      bottom: size.h
    };
  }

  function get_crop(layer, bounds) {
    return layer.crop != undefined
      && layer.crop.right > -1
      && layer.crop.bottom > -1 ? layer.crop : bounds;
  }

  function intersect(bounds, crop) {
    return {
      left: Math.max(crop.left, bounds.left),
      right: Math.min(crop.right, bounds.right),
      top: Math.max(crop.top, bounds.top),
      bottom: Math.min(crop.bottom, bounds.bottom),
    };
  }

  function has_size(rect) {
    return (rect.right - rect.left) > 0 && (rect.bottom - rect.top) > 0;
  }

  function offset_to(bounds, x, y) {
    return {
      left: bounds.left + x,
      right: bounds.right + x,
      top: bounds.top + y,
      bottom: bounds.bottom + y
    };
  }

  function transform_bounds(layer, parentBounds) {
    var result = parentBounds;
    var bounds = get_bounds(layer);
    var crop = get_crop(layer, bounds);
    if (has_size(bounds)) {
      result = offset_to(intersect(bounds, crop), layer.position.x, layer.position.y)
    }
    else if (has_size(crop)) {
      result = offset_to(crop, layer.position.x, layer.position.y)
    }
    result.label = layer.name;
    result.transform = layer.transform;
    return result;
  }

  /**
   * Checks if the layer is visible on screen accorindg to its type,
   * active buffer content, alpha and visible regions.
   *
   * @param {layer} layer
   * @returns if the layer is visible on screen or not
   */
  function is_visible(layer) {
    var visible = (layer.activeBuffer || layer.type === 'ColorLayer')
                  && !hidden && layer.color.a > 0;
    if (visible && layer.visibleRegion != undefined) {
      var isRectVisible = layer.visibleRegion.rect.some(has_size);
      visible &= isRectVisible;
    }
    return visible
  }

  var chips = [];
  var rect = transform_bounds(layer, parentBounds);
  var hidden = (layer.flags & FLAG_HIDDEN) != 0 || parentHidden;
  var visible = is_visible(layer);
  if (visible) {
    chips.push(get_visible_chip());
  } else {
    rect = {left: 0, right: 0, top: 0, bottom: 0};
  }
  if (layer.zOrderRelativeOf !== -1) {
    chips.push(RELATIVE_Z_CHIP);
  }
  if (layer.zOrderRelativeParentOf !== undefined) {
    chips.push(RELATIVE_Z_PARENT_CHIP);
  }
  if (layer.missing) {
    chips.push(MISSING_LAYER);
  }

  var transform_layer_with_parent_hidden =
      (layer) => transform_layer(layer, {parentBounds: rect, parentHidden: hidden});

  return transform({
    obj: layer,
    kind: 'layer',
    name: layer.name,
    children: [
      [layer.resolvedChildren, transform_layer_with_parent_hidden],
    ],
    rect,
    highlight: has_size(rect) ? rect: undefined,
    chips,
    visible,
  });
}

function missingLayer(childId) {
  return {
    name: "layer #" + childId,
    missing: true,
    zOrderRelativeOf: -1,
  }
}

function transform_layers(layers) {
  var idToItem = {};
  var isChild = {}
  layers.layers.forEach((e) => {
    idToItem[e.id] = e;
  });
  layers.layers.forEach((e) => {
    e.resolvedChildren = [];
    if (Array.isArray(e.children)) {
      e.resolvedChildren = e.children.map(
          (childId) => idToItem[childId] || missingLayer(childId));
      e.children.forEach((childId) => {
        isChild[childId] = true;
      });
    }
    if (e.zOrderRelativeOf !== -1) {
      idToItem[e.zOrderRelativeOf].zOrderRelativeParentOf = e.id;
    }
  });

  var roots = layers.layers.filter((e) => !isChild[e.id]);

  function foreachTree(nodes, fun) {
    nodes.forEach((n) => {
      fun(n);
      foreachTree(n.children, fun);
    });
  }

  var idToTransformed = {};
  var transformed_roots = roots.map((r) =>
    transform_layer(r, {parentBounds: {left: 0, right: 0, top: 0, bottom: 0},
      parentHidden: false}));

  foreachTree(transformed_roots, (n) => {
    idToTransformed[n.obj.id] = n;
  });
  var flattened = [];
  layers.layers.forEach((e) => {
    flattened.push(idToTransformed[e.id]);
  });

  return transform({
    obj: {},
    kind: 'layers',
    name: 'layers',
    children: [
      [transformed_roots, (c) => c],
    ],
    rects_transform (r) {
      var res = [];
      flattened.forEach((l) => {
        if (l.rect) {
          res.push(l.rect);
        }
      });
      return res.reverse();
    },
    flattened,
  });
}

function transform_layers_entry(entry) {
  return transform({
    obj: entry,
    kind: 'entry',
    name: nanos_to_string(entry.elapsedRealtimeNanos) + " - " + entry.where,
    children: [
      [[entry.layers], transform_layers],
    ],
    timestamp: entry.elapsedRealtimeNanos,
    stableId: 'entry',
  });
}

function transform_layers_trace(entries) {
  return transform({
    obj: entries,
    kind: 'layerstrace',
    name: 'layerstrace',
    children: [
      [entries.entry, transform_layers_entry],
    ],
  });
}

export {transform_layers, transform_layers_trace};
