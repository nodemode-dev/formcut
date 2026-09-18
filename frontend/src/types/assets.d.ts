declare module "*.css";
declare module "*?url" {
  const url: string;
  export default url;
}
declare const __APP_VERSION__: string;
