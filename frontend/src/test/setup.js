import '@testing-library/jest-dom'

// jsdom doesn't implement scrollIntoView; AlignPage calls it on every
// message update, which would otherwise throw in any test that renders it.
Element.prototype.scrollIntoView = () => {}
