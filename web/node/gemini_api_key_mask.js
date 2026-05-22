import { app } from "/scripts/app.js";

const API_KEY_WIDGET_NAME = ["password", "api_key"];

app.registerExtension({
    name: "comfy_nanobanana.gemini_api_key_mask",
    
    async beforeRegisterNodeDef(nodeType, nodeData, appRef) {
        if (!nodeData) return;

        // Store original onNodeCreated
        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        
        // Override onNodeCreated
        nodeType.prototype.onNodeCreated = function() {
            // Call original first
            if (origOnNodeCreated) {
                origOnNodeCreated.apply(this, arguments);
            }
            
            // Get reference to this node
            const node = this;

            // Find the api_key widget
            const apiKeyWidget = node.widgets?.find(w => API_KEY_WIDGET_NAME.includes(w.name));
            if (apiKeyWidget) {
                console.log("[NanoBanana] Setting up API key masking for widget:", apiKeyWidget);
                
                // Use properties on the widget to avoid closure issues
                apiKeyWidget._actualApiKey = (apiKeyWidget.value && !apiKeyWidget.value.includes("*")) ? apiKeyWidget.value : "";
                apiKeyWidget._isShowingReal = false;
                
                // Helper function to mask the API key
                function maskApiKey(key) {
                    if (!key || key.length === 0) return "";

                    // For short keys, mask everything
                    if (key.length <= 6) {
                        return "*".repeat(key.length);
                    }

                    // Show first 2 and last 2 characters
                    const firstPart = key.substring(0, 2);
                    const lastPart = key.substring(key.length - 2);
                    const maskLength = Math.max(10, key.length - 6);
                    
                    return firstPart + "*".repeat(maskLength) + lastPart;
                }
                
                // Store the original callback
                const origCallback = apiKeyWidget.callback;
                
                // Override the callback to capture real value
                apiKeyWidget.callback = function(v) {
                    // Skip if the value is masked (contains asterisks)
                    if (v && v.includes("*")) {
                        // Don't update with masked value
                        this.value = this._isShowingReal ? this._actualApiKey : maskApiKey(this._actualApiKey);
                        return;
                    }
                    
                    // Store the actual value
                    this._actualApiKey = v || "";
                    
                    // Call original callback if it exists
                    if (origCallback) {
                        origCallback.call(this, this._actualApiKey);
                    }
                    
                    // Update display
                    if (!this._isShowingReal) {
                        this.value = maskApiKey(this._actualApiKey);
                    }
                };
                
                // Store actual value getter for serialization
                apiKeyWidget.getActualValue = function() {
                    return this._actualApiKey || "";
                };
                
                // Override serialization - keep API key for API format
                apiKeyWidget.serializeValue = function() {
                    return this._actualApiKey || "";
                };
                
                // Override computeSize to ensure the widget value is used correctly
                const origComputeSize = apiKeyWidget.computeSize;
                if (origComputeSize) {
                    apiKeyWidget.computeSize = function(width) {
                        // Temporarily store the display value
                        const tempVal = this.value;
                        // Use actual value for computation
                        this.value = this._actualApiKey || "";
                        const result = origComputeSize.call(this, width);
                        // Restore display value
                        this.value = tempVal;
                        return result;
                    };
                }

                // Initial mask if value exists
                if (apiKeyWidget.value && !apiKeyWidget.value.includes("*")) {
                    apiKeyWidget._actualApiKey = apiKeyWidget.value;
                    apiKeyWidget.value = maskApiKey(apiKeyWidget._actualApiKey);
                }
                
                console.log("[NanoBanana] API key masking setup complete");
            }
        };
        
        // Override onSerialize to EXCLUDE API key from exports
        const origOnSerialize = nodeType.prototype.onSerialize;
        nodeType.prototype.onSerialize = function(o) {
            if (origOnSerialize) {
                origOnSerialize.call(this, o);
            }
            
            // Find api_key widget and REMOVE it from export
            const apiKeyWidget = this.widgets?.find(w => API_KEY_WIDGET_NAME.includes(w.name));
            if (apiKeyWidget) {
                const widgetIdx = this.widgets.indexOf(apiKeyWidget);
                if (widgetIdx >= 0 && o.widgets_values) {
                    // Set to empty string instead of actual value for security
                    o.widgets_values[widgetIdx] = "";
                    console.log("[NanoBanana] API key excluded from workflow export for security");
                }
            }
        };
        
        // Override onConfigure to handle loading
        const origOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function(o) {
            if (origOnConfigure) {
                origOnConfigure.call(this, o);
            }
            
            // After configuration, handle API key if present
            requestAnimationFrame(() => {
                const apiKeyWidget = this.widgets?.find(w => API_KEY_WIDGET_NAME.includes(w.name));
                if (apiKeyWidget && o.widgets_values) {
                    const widgetIdx = this.widgets.indexOf(apiKeyWidget);
                    if (widgetIdx >= 0) {
                        const value = o.widgets_values[widgetIdx];
                        if (value && value !== "" && !value.includes("*")) {
                            // This is a real API key from an old workflow, store it and mask display
                            if (apiKeyWidget.getActualValue) {
                                apiKeyWidget.callback(value);
                            } else {
                                apiKeyWidget.value = value;
                            }
                            console.log("[NanoBanana] Loaded API key from workflow (consider re-saving to exclude it)");
                        } else if (!value || value === "") {
                            // No API key in workflow (expected for new secure exports)
                            console.log("[NanoBanana] No API key in workflow - please enter it manually or use GEMINI_API_KEY env variable");
                        }
                    }
                }
            });
        };
        
        return nodeType;
    }
});