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


import jsonProtoDefs from 'frameworks/base/core/proto/android/server/windowmanagertrace.proto'
import jsonProtoDefsSF from 'frameworks/native/services/surfaceflinger/layerproto/layerstrace.proto'
import jsonProtoDefsTrans from 'frameworks/native/cmds/surfacereplayer/proto/src/trace.proto'
import protobuf from 'protobufjs'
import { transform_layers, transform_layers_trace } from './transform_sf.js'
import { transform_window_service, transform_window_trace } from './transform_wm.js'
import { transform_transaction_trace } from './transform_transaction.js'
import { fill_transform_data } from './matrix_utils.js'
import { mp4Decoder } from './decodeVideo.js'

var protoDefs = protobuf.Root.fromJSON(jsonProtoDefs)
  .addJSON(jsonProtoDefsSF.nested)
  .addJSON(jsonProtoDefsTrans.nested);

var WindowTraceMessage = protoDefs.lookupType(
  "com.android.server.wm.WindowManagerTraceFileProto");
var WindowMessage = protoDefs.lookupType(
  "com.android.server.wm.WindowManagerServiceDumpProto");
var LayersMessage = protoDefs.lookupType("android.surfaceflinger.LayersProto");
var LayersTraceMessage = protoDefs.lookupType("android.surfaceflinger.LayersTraceFileProto");
var TransactionMessage = protoDefs.lookupType("Trace");

const LAYER_TRACE_MAGIC_NUMBER = [0x09, 0x4c, 0x59, 0x52, 0x54, 0x52, 0x41, 0x43, 0x45] // .LYRTRACE
const WINDOW_TRACE_MAGIC_NUMBER = [0x09, 0x57, 0x49, 0x4e, 0x54, 0x52, 0x41, 0x43, 0x45] // .WINTRACE
const MPEG4_MAGIC_NMBER = [0x00, 0x00, 0x00, 0x18, 0x66, 0x74, 0x79, 0x70, 0x6d, 0x70, 0x34, 0x32] // ....ftypmp42

const DATA_TYPES = {
  WINDOW_MANAGER: {
    name: "WindowManager",
    icon: "view_compact",
  },
  SURFACE_FLINGER: {
    name: "SurfaceFlinger",
    icon: "filter_none",
  },
  SCREEN_RECORDING: {
    name: "Screen recording",
    icon: "videocam",
  },
  TRANSACTION: {
    name: "Transaction",
    icon: "timeline",
  },
}

const FILE_TYPES = {
  'window_trace': {
    name: "WindowManager trace",
    dataType: DATA_TYPES.WINDOW_MANAGER,
    decoder: protoDecoder,
    decoderParams: {
      protoType: WindowTraceMessage,
      transform: transform_window_trace,
      timeline: true,
    },
  },
  'layers_trace': {
    name: "SurfaceFlinger trace",
    dataType: DATA_TYPES.SURFACE_FLINGER,
    decoder: protoDecoder,
    decoderParams: {
      protoType: LayersTraceMessage,
      transform: transform_layers_trace,
      timeline: true,
    },
  },
  'layers_dump': {
    name: "SurfaceFlinger dump",
    dataType: DATA_TYPES.SURFACE_FLINGER,
    decoder: protoDecoder,
    decoderParams: {
      protoType: LayersMessage,
      transform: transform_layers,
      timeline: false,
    },
  },
  'window_dump': {
    name: "WindowManager dump",
    dataType: DATA_TYPES.WINDOW_MANAGER,
    decoder: protoDecoder,
    decoderParams: {
      protoType: WindowMessage,
      transform: transform_window_service,
      timeline: false,
    },
  },
  'screen_recording': {
    name: "Screen recording",
    dataType: DATA_TYPES.SCREEN_RECORDING,
    decoder: videoDecoder,
    decoderParams: {
      videoDecoder: mp4Decoder,
    },
  },
  'transaction': {
    name: "Transaction",
    dataType: DATA_TYPES.TRANSACTION,
    decoder: protoDecoder,
    decoderParams: {
      protoType: TransactionMessage,
      transform: transform_transaction_trace,
      timeline: true,
    }
  }
};

// Replace enum values with string representation and
// add default values to the proto objects. This function also handles
// a special case with TransformProtos where the matrix may be derived
// from the transform type.
function modifyProtoFields(protoObj, displayDefaults) {
  if (!protoObj || protoObj !== Object(protoObj) || !protoObj.$type) {
    return;
  }
  for (var fieldName in protoObj.$type.fields) {
    var fieldProperties = protoObj.$type.fields[fieldName];
    var field = protoObj[fieldName];

    if (Array.isArray(field)) {
      field.forEach((item, _) => {
        modifyProtoFields(item, displayDefaults);
      })
      continue;
    }

    if (displayDefaults && !(field)) {
      protoObj[fieldName] = fieldProperties.defaultValue;
    }

    if (fieldProperties.type === 'TransformProto') {
      fill_transform_data(protoObj[fieldName]);
      continue;
    }

    if (fieldProperties.resolvedType && fieldProperties.resolvedType.valuesById) {
      protoObj[fieldName] = fieldProperties.resolvedType.valuesById[protoObj[fieldProperties.name]];
      continue;
    }
    modifyProtoFields(protoObj[fieldName], displayDefaults);
  }
}

function protoDecoder(buffer, fileType, fileName, store) {
  var decoded = fileType.decoderParams.protoType.decode(buffer);
  modifyProtoFields(decoded, store.displayDefaults);
  var transformed = fileType.decoderParams.transform(decoded);
  var data
  if (fileType.decoderParams.timeline) {
    data = transformed.children;
  } else {
    data = [transformed];
  }
  return dataFile(fileName, data.map(x => x.timestamp), data, fileType.dataType);
}

function videoDecoder(buffer, fileType, fileName, store) {
  var [data, timeline] = fileType.decoderParams.videoDecoder(buffer)
  return dataFile(fileName, timeline, data, fileType.dataType);
}

function dataFile(filename, timeline, data, type) {
  return {
    filename: filename,
    timeline: timeline,
    data: data,
    type: type,
    selectedIndex: 0,
  }
}

function arrayEquals(a, b) {
  if (a.length !== b.length) {
    return false;
  }
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) {
      return false;
    }
  }
  return true;
}

function arrayStartsWith(array, prefix) {
  return arrayEquals(array.slice(0, prefix.length), prefix);
}

function decodedFile(fileType, buffer, fileName, store) {
  return [fileType, fileType.decoder(buffer, fileType, fileName, store)];
}

function detectAndDecode(buffer, fileName, store) {
  if (arrayStartsWith(buffer, LAYER_TRACE_MAGIC_NUMBER)) {
    return decodedFile(FILE_TYPES['layers_trace'], buffer, fileName, store);
  }
  if (arrayStartsWith(buffer, WINDOW_TRACE_MAGIC_NUMBER)) {
    return decodedFile(FILE_TYPES['window_trace'], buffer, fileName, store);
  }
  if (arrayStartsWith(buffer, MPEG4_MAGIC_NMBER)) {
    return decodedFile(FILE_TYPES['screen_recording'], buffer, fileName, store);
  }
  for (var name of ['transaction', 'layers_dump', 'window_dump']) {
    try {
      return decodedFile(FILE_TYPES[name], buffer, fileName, store);
    } catch (ex) {
      // ignore exception and try next filetype
    }
  }
  throw new Error('Unable to detect file');
}

export { detectAndDecode, dataFile, DATA_TYPES, FILE_TYPES };
