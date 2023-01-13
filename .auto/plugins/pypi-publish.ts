import { Auto, IPlugin } from "@auto-it/core";


export default class PyPIPublishPlugin implements IPlugin {
    name = "PyPIPublish";

    /** Tap into auto plugin points. */
    apply(auto: Auto) {
        // Commit new version
        auto.hooks.version.tapPromise(this.name, async ({ bump }) => {
            if (!bump) {
                auto.logger.log.info("No release found, doing nothing");
                return;
            }

            // TODO: Run poetry version `${bump}`
        });

        // Publish to PyPI
        auto.hooks.publish.tapPromise(this.name, async () => {
            // TODO
        });
    }
}
